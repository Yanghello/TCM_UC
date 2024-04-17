# -*- coding: utf-8 -*-
import os
import argparse
import requests
import json
import logging
import pandas as pd
import uuid
import re
import time
import sqlite3
import traceback

parser = argparse.ArgumentParser(description='Process some integers.')

parser.add_argument('--token', type=str, help='token from coze')
parser.add_argument('--bot_id', type=str, help='bot id')
parser.add_argument('--user', type=str, default=None, help='user_id')
parser.add_argument('--retry_times', type=int, default=3, help='post retry times')
parser.add_argument('--row_begin', type=int, default=0, help='row begin')
parser.add_argument('--row_end', type=int, default=1000, help='row end')
parser.add_argument('--mode', type=str, default="", help='o/a')
parser.add_argument('--out_file', type=str, default="验证数据集-逐个输出.xlsx", help='output file name')
parser.add_argument("--cache_db_file", type=str, default="response_cache.db", help='cache db file')


args = parser.parse_args()
logging.basicConfig(level=logging.DEBUG)

# Step 1: Connect to the SQLite database file (it will be created if it doesn't exist)
conn = sqlite3.connect(args.cache_db_file)

# Step 2: Create a cursor object using the connection
cursor = conn.cursor()

# Step 3: Create a table with columns 'id' and 'data'
# The 'IF NOT EXISTS' clause prevents an error if the table already exists
cursor.execute('''
CREATE TABLE IF NOT EXISTS response_cache (
    id INTEGER PRIMARY KEY,
    data TEXT
)
''')

def cache_exist(index):
    cursor.execute(f"SELECT * FROM response_cache WHERE id={index}")
    result = cursor.fetchone()
    if result is None:
        return False, None
    else:
        return True, result[1]

def add_cache(index, data):
    cursor.execute(f"INSERT INTO response_cache (id, data) VALUES ({index}, '{data}')")
    conn.commit()


def post_uc_request(query_data, conversation_id, stream=True):
    # Headers
    headers = {
        'Authorization': f'Bearer {args.token}',
        'Content-Type': 'application/json',
        'Accept': '*/*',
        'Host': 'api.coze.com',
        'Connection': 'keep-alive',
    }

    # Data payload
    data = {
        'conversation_id': conversation_id,
        'bot_id': args.bot_id,
        'user': args.user,
        'query': query_data,
        'stream': stream,
    }
    if not stream: 
        retry_times = args.retry_times
        while (retry_times > 0):
            # Make the request
            response = requests.post('https://api.coze.com/open_api/v2/chat', headers=headers, data=json.dumps(data))

            # Check if the request was successful
            if response.status_code == 200:
                return response.text
            else:
                print('Failed.')
                print(f'Status code: {response}, retry ...')
                retry_times -= 1
                time.sleep(1)

        raise Exception('retry failed.')
    else:
        timeout = 20 * 60 # 20 min
        # POST request to start streaming
        response = requests.post('https://api.coze.com/open_api/v2/chat', headers=headers, data=json.dumps(data), stream=True)

        # Initialize an empty string to hold concatenated content
        concatenated_content = ''

        # Check if response connection is kept alive
        if response.ok:
            try:
                # Iterate over the lines in the response
                now = time.time()
                for line in response.iter_lines():
                    # Filter out keep-alive new lines
                    time_cost = time.time() - now
                    if time_cost > timeout:
                        raise Exception('timeout')
                    if line:
                        decoded_line = line.decode('utf-8')
                        logging.info(f"response line: {decoded_line}")
                        if 'data:' in decoded_line:
                            # Strip the "data:" part and parse JSON
                            json_data = json.loads(decoded_line[5:])
                            # Check if the event is a message from the assistant
                            if json_data.get('event') == 'message':
                                message = json_data.get('message', {})
                                if message.get('type') != 'answer':
                                    continue
                                if message.get('role') == 'assistant':
                                    # Concatenate the content
                                    concatenated_content += message.get('content', '')
                            # Check if the stream is finished
                            if json_data.get('is_finish'):
                                logging.info('Stream finished.')
                                
            except KeyboardInterrupt:
                logging.error('Stream stopped by user.')

            except Exception as e:
                logging.error(f"Error: {e}")
            finally:
                # Close the stream connection
                response.close()
                # Output the concatenated content
                logging.info(f"Concatenated Content: {concatenated_content}")
                # raise Exception(f"response error")
        else:
            logging.error('Failed to connect to the stream')
            raise Exception(f"reponse not ok: {response}")

        return concatenated_content

# {
#   "messages": [
#     {
#       "role": "assistant",
#       "type": "answer",
#       "content": "Hello! How can I assist you today?",
#       "content_type": "text",
#       "extra_info": null
#     }
#   ],
#   "conversation_id": "123",
#   "code": 0,
#   "msg": "success"
# }

def parse_response(text, stream=True):
    if stream:
        return text

    data = json.loads(text)
    if data['code'] != 0:
        raise Exception(f'code: {data["code"]}, msg: {data["msg"]}')
    else:
        context = ""
        for message in data['messages']:
            if message['role'] == "assistant" and message['type'] == "answer":
                context += message['content']
            
        assert len(context) > 0, f"context is empty, data: {data}"
        return context

def get_excel_data(file_path, sheet_name, col_name, row_begin, row_end):
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    assert col_name[0] == "序号"
    condition = df[col_name[0]].between(row_begin, row_end)
    return df[condition]

# output dataframe to excel file with mode overwrite or append
def output_excel_data(file_path, sheet_name, data, mode):
    if mode == "o":
        with pd.ExcelWriter(file_path, engine='openpyxl', mode='w') as writer:
            data.to_excel(writer, sheet_name=sheet_name, index=False,)
    elif mode == "a":
        with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists="replace") as writer:
            data.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
    else:
        raise Exception("mode must be overwrite or append")

# parse from markdown json table to dataframe,such as
# ```json\n[\n  {\n    "症状简介": "反复黏液脓血便，腹痛，腹泻，里急后重，便前腹痛明显，左下腹胀满不适，肠鸣音亢进，失眠多梦，情绪不佳，口干口苦",\n    "推断理由": "患者的主要症状包括反复黏液脓血便，腹痛，腹泻，里急后重，这些症状符合大肠湿热证的主症。同时，患者还有便前腹痛明显，左下腹胀满不适，肠鸣音亢进，失眠多梦，情绪不佳，口干口苦等次症，舌红苔黄腻，脉弦细，这些都是大肠湿热证的典型表现。",\n    "推断症型": "1=大肠湿热"\n  },\n  {\n    "症状简介": "反复黏液脓血便，腹痛，腹泻，里急后重，便前腹痛明显，左下腹胀满不适，肠鸣音亢进，失眠多梦，情绪不佳，口干口苦",\n    "推断理由": "根据患者的情绪不佳，失眠多梦，以及口干口苦等症状，可以考虑肝郁脾虚证的可能性。患者的舌红苔黄腻，脉弦细也支持这一分型。",\n    "推断症型": "6=肝郁脾虚"\n  }\n]\n```
def parse_raw_data(raw_data):
    # Use regular expression to extract the JSON string from the Markdown code block
    match = re.search(r"```json\n(.*?)\n```", raw_data, re.DOTALL)
    if match:
        raw_data = match.group(1)
        # Parse the JSON string into a Python object
        try:
            raw_data_json = json.loads(raw_data)
            # Do something with the data
        except json.JSONDecodeError as e:
            raise Exception("Failed to parse JSON:", e)
    else:
        raise Exception("No JSON code block found.")

    # create datafram's colname ["症状简介", "推断理由",“推断症型”]
    col_name = ["症状简介", "推断理由","推断症型"]
    data = ["","",""]
    for index, item in enumerate(raw_data_json):
        data = [data[0] + f"({index}): {item[col_name[0]]}", data[1] + f"({index}): {item[col_name[1]]}", data[2] + f",{item[col_name[2]]}"]

    df = pd.DataFrame([data], columns=col_name)
    return df

def write_to_cache(input_str, cache_file_path, mode="a"):
    with open(cache_file_path, mode) as f:
        f.write(input_str + "\n")

if __name__ == "__main__":
    input_file_path = r"../UC_datasets/验证数据集-api-input.xlsx"
    sheet_name = "Sheet1"
    col_name = ["序号", "医案文本【证型选择：1=大肠湿热，2=热毒炽盛，3=脾虚湿蕴，4=寒热错杂，5=瘀阻肠络，6=肝郁脾虚，7=脾肾阳虚】"]
    row_begin = args.row_begin
    row_end = args.row_end
    data = get_excel_data(input_file_path, sheet_name, col_name, row_begin, row_end)
    stream = True

    out_data = None
    retry_times = args.retry_times
    while (retry_times > 0):
        try:
            for index, row in data.iterrows():
                # time.sleep(1)
                logging.info(f"start process index {index}/{len(data)}")
                query_data = row[col_name[1]]
                #random conversion_id
                conversation_id = str(uuid.uuid4())
                exist, response = cache_exist(row[col_name[0]])
                if not exist:
                    try:
                        response = post_uc_request(query_data, conversation_id, stream)
                        write_to_cache(str(row[col_name[0]]) + "," + response,  "response.cache")
                        # response = '{"messages":[{"role":"assistant","type":"knowledge","content":"---\\nrecall slice 1:\\n辨证分型 1. 大肠湿热证 主症： ①腹泻， 便下黏液脓血； ②腹痛； ③ 里 急 后 重 。次 症 ：① 肛 门 灼 热 ；② 腹 胀 ；③ 小 便 短 赤 ；④ 口 干 ；⑤ 口 苦 。舌 脉 ：① 舌 质 红 ，苔 黄 腻 ；② 脉 滑 。 2. 热毒炽盛证 主症： ①便下脓血或血便， 量多次频； ② 腹 痛 明 显 ；③ 发 热 。次 症 ：① 里 急 后 重 ；② 腹 胀 ；③ 口 渴 ； ④烦躁不安。 舌脉： ①舌质红， 苔黄燥； ②脉滑数。 3. 脾虚湿蕴证 主症： ①黏液脓血便， 白多赤少 ， 或为白 冻； ②腹泻便溏， 夹有不消化食物； ③脘腹胀满。 次症： ①腹部 隐 痛 ；② 肢 体 困 倦 ；③ 食 少 纳 差 ；④ 神 疲 懒 言 。舌 脉 ：① 舌 质 淡红， 边有齿痕， 苔薄白腻； ②脉细弱或细滑。 4. 寒热错杂证 主症： ①下痢稀薄， 夹有黏冻， 反复发作； ② 肛 门 灼 热 ；③ 腹 痛 绵 绵 。次 症 ：① 畏 寒 怕 冷 ；② 口 渴 不 欲 饮 ； ③ 饥 不 欲 食 舌 脉 ：① 舌 质 红 ，或 舌 淡 红 ，苔 薄 黄 ；② 脉 弦 ，或 细弦。 5. 肝郁脾虚证 主症： ①情绪抑郁或焦虑不安， 常因情志 因 素 诱 发 大 便 次 数 增 多 ；② 大 便 稀 烂 或 黏 液 便 ；③ 腹 痛 即 泻 ， 泻 后 痛 减 。次 症 ：① 排 便 不 爽 ；② 饮 食 减 少 ；③ 腹 胀 ；④ 肠 鸣 。 舌 脉 ：① 舌 质 淡 红 ，苔 薄 白 ；② 脉 弦 或 弦 细 。 6. 脾肾阳虚证 主症： ①久泻不止， 大便稀薄； ②夹有白 冻， 或伴有完谷不化， 甚则滑脱不禁； ③腹痛喜温喜按。 次症： ① 腹 胀 ；② 食 少 纳 差 ；③ 形 寒 肢 冷 ；④ 腰 酸 膝 软 。舌 脉 ：① 舌 质 淡胖， 或有齿痕， 苔薄白润； ②脉沉细。 7. 阴血亏虚证 主症： ①便下脓血， 反复发作； ②大便干 结， 夹有黏液便血， 排便不畅； ③腹中隐隐灼痛。 次症： ①形体 消 瘦 ；② 口 燥 咽 干 ；③ 虚 烦 失 眠 ；④ 五 心 烦 热 。舌 脉 ：① 舌 红 少 津 或 舌 质 淡 ，少 苔 或 无 苔 ；② 脉 细 弱 。 证候诊断： 主症2项， 次症2项， 参考舌脉， 即可诊断。\\n---\\nrecall slice 2:\\n3.7 阴血亏虚证 治法： 滋阴清肠， 益气养血 主方 ： 驻车丸 （《 备 急 千 金 要 方 》） 合 四 物 汤 （《 太 平 惠 民 和 剂 局 方 》）。药 物 ： 黄连、 阿胶、 干姜、 当归、 地黄、 白芍、 川芎。 加减： 大便干结， 加 麦冬、 玄参、 火麻仁等； 面色少华， 加黄芪、 党参等。 4. 中药灌肠 中药灌肠有助于较快缓解症状， 促进肠黏膜 损伤的修复。 常用药物有： ①清热化湿类： 黄柏、 黄连、 苦参、 白头翁、 马齿苋、 秦皮等； ②收敛护膜类： 诃子、 赤石脂、 石榴 皮 、五 倍 子 、乌 梅 、枯 矾 等 ；③ 生 肌 敛 疡 类 ：白 及 、三 七 、血 竭 、 青黛、 儿茶、 生黄芪、 炉甘石等； ④宁络止血类： 地榆、 槐花、 紫草、 紫珠叶 、 蒲黄、 大黄炭、 仙鹤草等； ⑤清热解毒类： 野菊 花、 白花蛇舌草、 败酱草等。 临床可根据病情需要选用4-8味 中药组成灌肠处方。 灌肠液以120-150mL， 温度39℃， 睡前排 便后灌肠为宜， 可取左侧卧位30min， 平卧位30min， 右侧卧位 3 0 m i n ，后 取 舒 适 体 位 。灌 肠 结 束 后 ，尽 量 保 留 药 液 1 h 以 上 。 5. 常用中成药 5.1 虎地肠溶胶囊 清热、 利湿、 凉血。 用于UC湿热蕴结 证， 症见腹痛， 下痢脓血， 里急后重。 5.2 补脾益肠丸 益气养血， 温阳行气， 涩肠止泻。 用于脾 虚气滞所致的泄泻， 症见腹胀疼痛、 肠鸣泄泻、 黏液血便； 慢性 结 肠 炎 、U C 见 上 述 证 候 者 。 5.3 固本益肠片 健脾温肾 ， 涩肠止泻。 用于脾虚或脾肾 阳虚所致的泄泻。 症见腹痛绵绵、 大便清稀或有黏液及黏液血 便 、食 少 腹 胀 、腰 痠乏力、 形寒肢冷、 舌淡苔白、 脉虚； 慢性肠 炎见上述证候者\\n---\\nrecall slice 3:\\n5 诊断 5.1 西医诊断 临床表现、 相关检查（实验室检 查、结肠镜检查、黏膜组织活检） 、诊断要点、临床 类型[12]、病变范围[13]、病情分期[14]、严重程度分级[8] 均参照《炎症性肠病诊断与治疗的共识意见 （2018年•北京） 》 [15]及美国胃肠病学会（ American College of Gastroenterology ，ACG）临床实践指南 （2019） [8]。 5.2 中医辨证分型 经专家共识确定证型如下。 （1）湿热蕴肠证： 主症： 腹痛，腹泻，便下黏液脓血； 里急后重，肛门灼热。次症： 身热； 小便短赤； 口干口 苦；口臭。舌脉：舌质红，苔黄腻，脉滑数。 （ 2）热 毒炽盛证：主症：便下脓血或血便，量多次频；发热。次症： 里急后重； 腹胀； 口渴； 烦躁不安； 腹痛明显。 舌脉：舌质红，苔黄燥，脉滑数。 （ 3）浊毒内蕴证： 主症： 大便脓血并重； 里急后重，大便黏腻、排便不爽。 次症：口干口苦、口黏；头身困重；面色秽滞；小便短 赤不利；腹痛。舌脉：舌质红，苔黄腻，脉弦滑。 （ 4） 脾虚湿蕴证： 主症： 腹泻，夹有不消化食物； 黏液脓 血便，白多赤少，或为白冻。次症： 肢体倦怠，神疲 懒言；腹部隐痛；脘腹胀满；食少纳差。舌脉：舌质淡 红，边有齿痕，苔白腻，脉细弱或细滑。 （ 5）寒热错 杂证： 主症： 下痢稀薄，夹有黏冻； 反复发作次症： 四肢不温；腹部灼热；腹痛绵绵；口渴不欲饮。舌脉： 舌质红或淡红，苔薄黄，脉弦或细弦。 （ 6）肝郁脾 虚证：主症：常因情志因素诱发大便次数增多；大便 稀烂或黏液便；腹痛即泻，泻后痛减。次症：排便不 爽； 饮食减少； 腹胀； 肠鸣。舌脉： 舌质淡红，苔薄白， 脉弦或弦细。 （ 7）瘀阻肠络证：主症： 腹痛拒按，痛 有定处；下利脓血、血色暗红或夹有血块。次症：面 色晦暗； 腹部有痞块； 胸胁胀痛； 肌肤甲错； 泻下不爽。 舌脉： 舌质暗红，有瘀点瘀斑，脉涩或弦。 （ 8）脾肾 阳虚证： 主症： 久泻不止，大便稀薄； 夹有白冻，或 伴有完谷不化， 甚则滑脱不禁。次症： 腹胀； 食少纳差； 腹痛喜温喜按； 形寒肢冷； 腰酸膝软。舌脉： 舌质淡胖， 或有齿痕，苔薄白润，脉沉细。注： 以上 8个证候的 确定，凡具备主症 2项，加次症 2项即可诊断，舌脉\\n---\\nrecall slice 4:\\n病变部位于右半结肠 或病变范围较广者，推荐使用经内镜肠道置管术 [37] （transendoscopic enteral tubing ， TET）进行中药汤 剂或中西医结合保留灌肠（专家共识，弱推荐） 。结 肠TET操作方法： （ 1）患者左侧卧位，静脉麻醉或 清醒状态； （ 2）医生进镜至回盲部，沿活检孔插入 TET导 管 ；（ 3）植入导管至回盲部，植入长度在成人 约85 cm；（ 4）经内镜下送入组织夹将 TET管的绳圈 固定到肠皱襞，依据保留时长的需求选择组织夹的数 量，1~4枚，多为 2~3枚可满足 1~2周保留置管需求； （5）退镜后拔出管内导丝； （ 6）妥善固定 TET管体 外段于左侧臀部； （ 7）将粪菌悬液或灌肠药物溶液通 过TET注入肠道深部； （ 8）TET管可自然脱落，也 可在治疗结束后手动拔除。 对于中西药物不耐受、无效或难治的患者可以尝 试粪菌移植疗法（ fecal microbiota transplantation ， FMT）[38-40 ]（高，弱推荐） ，或骶神经刺激疗法[41] （低，弱推荐） ，或选择性白细胞吸附疗法[42]（高， 弱推荐） 。 （ 1）FMT 是一种新兴疗法，目前已经证明 FMT治疗 UC的长期疗效和安全性，但目前 FMT尚 未广泛应用，对于中西药物过敏、无效或难治的患者图1 UC病证结合诊断流程血常规、粪便常规 +潜血 +便培养， 肠镜 +病理检查、ESR、CRP 腹痛、腹泻，黏液脓血便 进一步检查 除外其他疾病相应治疗 辨 证 分 型确 诊 U C湿热蕴肠证 寒热错杂证浊毒内蕴证 瘀阻肠络证肝郁脾虚证脾虚湿蕴证热毒炽盛证初发型 活动期慢性复发型 缓解期 脾肾阳虚证临床类型 病情分期直肠型 左半结肠型 广泛结肠型病变范围 轻度 中度 重度严重程度分级\\n---\\nrecall slice 5:\\n3. 随访 应重视对本病癌变的监测， 按病情定期进行肠 镜检查[25]，若 为 直 肠 型 ，无 需 肠 镜 监 测 ，广 泛 性 结 肠 炎 或 左 半 结肠炎患者， 从最初症状出现后的第8年起， 每1-2年 （高风险 者 ） 或者每3-4年 （ 低风险者 ） 行肠镜检查。 风险评判主要依据 4条： 全结肠炎、 内镜下和/或病理组织学的炎性反应 （糜烂、 溃 疡/基底浆细胞增多， 重度、 弥漫性黏膜全层和固有层细胞增 加 ） 、 假息肉、 结直肠癌家族史。 低风险者具备0-2条， 高风险 者具备3-4条。 伴有原发性硬化性胆管炎的患者发生结肠癌风 险较高， 应每年进行肠镜监测。 对高度疑为癌变及确诊为癌变 者及 时 行 手术 治 疗\\n---\\nrecall slice 6:\\n3.3. 脾虚湿蕴型 \\n脾虚在 UC发病及病变过程中起重要作用 ，并贯穿于本病的始终 ，脾虚是 UC复发之根本 ，因此健\\n脾补肾、调和气血是本病维持缓解、防止复发的首要治法，同时兼以清肠化湿[4]。其主要临床表现为下\\n利黏液血便、白多赤少，大便溏薄，腹胀，少气懒言，易疲劳，舌淡边有齿痕。治法以益气健脾、化湿\\n和中，以参苓白术散 (《太平惠民和剂局方》 )为主方，方中以四君子汤( 党参、白术、茯苓、甘草) 平补脾\\n胃之气为君，加入和胃理气渗湿之品如扁豆、苡仁、山药、莲子，既可健脾，又能渗湿止泻，标本兼顾，\\n佐以砂仁芳香醒脾，助四君促进中焦运化，畅通气机。大便白冻黏液较多者，加\\n","content_type":"text"},{"role":"assistant","type":"answer","content":"```json\\n[\\n{\\n\\"症状简介\\":\\"患者出现反复黏液脓血便，伴随腹痛、腹泻，肠镜检查显示黏膜充血，点片状糜烂，血管网模糊，符合溃疡性结肠炎的表现。近期症状为排稀软便，便中带有大量黏液及少量脓血，血色鲜红，伴有腹泻、里急后重，便前腹痛，偶有左下腹胀满不适，肠鸣音亢进，失眠多梦，情绪不佳，时有口干口苦。\\",\\n\\"推断理由\\":\\"患者的主症包括反复黏液脓血便、腹痛、腹泻、里急后重，次症包括左下腹胀满不适、肠鸣音亢进、失眠多梦、情绪不佳、口干口苦，舌红苔黄腻，脉弦细。根据中医辨证分型，主症和次症结合舌脉表现，可推断为大肠湿热证和肝郁脾虚证。\\",\\n\\"推断症型\\":\\"1=大肠湿热，6=肝郁脾虚\\"\\n},\\n{\\n\\"症状简介\\":\\"患者有反复黏液脓血便，腹痛、腹泻，肠镜检查符合溃疡性结肠炎，近期症状包括排稀软便，便中带有大量黏液及少量脓血，血色鲜红，伴有腹泻、里急后重，便前腹痛，左下腹胀满不适，肠鸣音亢进，失眠多梦，情绪不佳，口干口苦。\\",\\n\\"推断理由\\":\\"患者的症状与热毒炽盛证的主症和次症相符，如便下脓血或血便，量多次频；腹痛明显；发热。次症包括里急后重；腹胀；口渴；烦躁不安。舌脉表现为舌质红，苔黄燥，脉滑数。虽然患者未明确描述发热症状，但其他症状与热毒炽盛证相符合。\\",\\n\\"推断症型\\":\\"2=热毒炽盛\\"\\n}\\n]\\n```","content_type":"text"},{"role":"assistant","type":"verbose","content":"{\\"msg_type\\":\\"generate_answer_finish\\",\\"data\\":\\"\\"}","content_type":"text"}],"conversation_id":"6af953b4-865a-48cd-a24b-f7098f0e156d","code":0,"msg":"success"}'
                        logging.info(f"query_data: {query_data}, conversation_id: {conversation_id}, response: {response}")
                        raw_output_data = parse_response(response, stream)
                        output_data = parse_raw_data(raw_output_data)
                        add_cache(row[col_name[0]], response)
                    except Exception as e:
                        logging.error(f"index {row[col_name[0]]} failed, will skip. error: {e}")
                        continue
                # response = '{"messages":[{"role":"assistant","type":"knowledge","content":"---\\nrecall slice 1:\\n辨证分型 1. 大肠湿热证 主症： ①腹泻， 便下黏液脓血； ②腹痛； ③ 里 急 后 重 。次 症 ：① 肛 门 灼 热 ；② 腹 胀 ；③ 小 便 短 赤 ；④ 口 干 ；⑤ 口 苦 。舌 脉 ：① 舌 质 红 ，苔 黄 腻 ；② 脉 滑 。 2. 热毒炽盛证 主症： ①便下脓血或血便， 量多次频； ② 腹 痛 明 显 ；③ 发 热 。次 症 ：① 里 急 后 重 ；② 腹 胀 ；③ 口 渴 ； ④烦躁不安。 舌脉： ①舌质红， 苔黄燥； ②脉滑数。 3. 脾虚湿蕴证 主症： ①黏液脓血便， 白多赤少 ， 或为白 冻； ②腹泻便溏， 夹有不消化食物； ③脘腹胀满。 次症： ①腹部 隐 痛 ；② 肢 体 困 倦 ；③ 食 少 纳 差 ；④ 神 疲 懒 言 。舌 脉 ：① 舌 质 淡红， 边有齿痕， 苔薄白腻； ②脉细弱或细滑。 4. 寒热错杂证 主症： ①下痢稀薄， 夹有黏冻， 反复发作； ② 肛 门 灼 热 ；③ 腹 痛 绵 绵 。次 症 ：① 畏 寒 怕 冷 ；② 口 渴 不 欲 饮 ； ③ 饥 不 欲 食 舌 脉 ：① 舌 质 红 ，或 舌 淡 红 ，苔 薄 黄 ；② 脉 弦 ，或 细弦。 5. 肝郁脾虚证 主症： ①情绪抑郁或焦虑不安， 常因情志 因 素 诱 发 大 便 次 数 增 多 ；② 大 便 稀 烂 或 黏 液 便 ；③ 腹 痛 即 泻 ， 泻 后 痛 减 。次 症 ：① 排 便 不 爽 ；② 饮 食 减 少 ；③ 腹 胀 ；④ 肠 鸣 。 舌 脉 ：① 舌 质 淡 红 ，苔 薄 白 ；② 脉 弦 或 弦 细 。 6. 脾肾阳虚证 主症： ①久泻不止， 大便稀薄； ②夹有白 冻， 或伴有完谷不化， 甚则滑脱不禁； ③腹痛喜温喜按。 次症： ① 腹 胀 ；② 食 少 纳 差 ；③ 形 寒 肢 冷 ；④ 腰 酸 膝 软 。舌 脉 ：① 舌 质 淡胖， 或有齿痕， 苔薄白润； ②脉沉细。 7. 阴血亏虚证 主症： ①便下脓血， 反复发作； ②大便干 结， 夹有黏液便血， 排便不畅； ③腹中隐隐灼痛。 次症： ①形体 消 瘦 ；② 口 燥 咽 干 ；③ 虚 烦 失 眠 ；④ 五 心 烦 热 。舌 脉 ：① 舌 红 少 津 或 舌 质 淡 ，少 苔 或 无 苔 ；② 脉 细 弱 。 证候诊断： 主症2项， 次症2项， 参考舌脉， 即可诊断。\\n---\\nrecall slice 2:\\n3.7 阴血亏虚证 治法： 滋阴清肠， 益气养血 主方 ： 驻车丸 （《 备 急 千 金 要 方 》） 合 四 物 汤 （《 太 平 惠 民 和 剂 局 方 》）。药 物 ： 黄连、 阿胶、 干姜、 当归、 地黄、 白芍、 川芎。 加减： 大便干结， 加 麦冬、 玄参、 火麻仁等； 面色少华， 加黄芪、 党参等。 4. 中药灌肠 中药灌肠有助于较快缓解症状， 促进肠黏膜 损伤的修复。 常用药物有： ①清热化湿类： 黄柏、 黄连、 苦参、 白头翁、 马齿苋、 秦皮等； ②收敛护膜类： 诃子、 赤石脂、 石榴 皮 、五 倍 子 、乌 梅 、枯 矾 等 ；③ 生 肌 敛 疡 类 ：白 及 、三 七 、血 竭 、 青黛、 儿茶、 生黄芪、 炉甘石等； ④宁络止血类： 地榆、 槐花、 紫草、 紫珠叶 、 蒲黄、 大黄炭、 仙鹤草等； ⑤清热解毒类： 野菊 花、 白花蛇舌草、 败酱草等。 临床可根据病情需要选用4-8味 中药组成灌肠处方。 灌肠液以120-150mL， 温度39℃， 睡前排 便后灌肠为宜， 可取左侧卧位30min， 平卧位30min， 右侧卧位 3 0 m i n ，后 取 舒 适 体 位 。灌 肠 结 束 后 ，尽 量 保 留 药 液 1 h 以 上 。 5. 常用中成药 5.1 虎地肠溶胶囊 清热、 利湿、 凉血。 用于UC湿热蕴结 证， 症见腹痛， 下痢脓血， 里急后重。 5.2 补脾益肠丸 益气养血， 温阳行气， 涩肠止泻。 用于脾 虚气滞所致的泄泻， 症见腹胀疼痛、 肠鸣泄泻、 黏液血便； 慢性 结 肠 炎 、U C 见 上 述 证 候 者 。 5.3 固本益肠片 健脾温肾 ， 涩肠止泻。 用于脾虚或脾肾 阳虚所致的泄泻。 症见腹痛绵绵、 大便清稀或有黏液及黏液血 便 、食 少 腹 胀 、腰 痠乏力、 形寒肢冷、 舌淡苔白、 脉虚； 慢性肠 炎见上述证候者\\n---\\nrecall slice 3:\\n5 诊断 5.1 西医诊断 临床表现、 相关检查（实验室检 查、结肠镜检查、黏膜组织活检） 、诊断要点、临床 类型[12]、病变范围[13]、病情分期[14]、严重程度分级[8] 均参照《炎症性肠病诊断与治疗的共识意见 （2018年•北京） 》 [15]及美国胃肠病学会（ American College of Gastroenterology ，ACG）临床实践指南 （2019） [8]。 5.2 中医辨证分型 经专家共识确定证型如下。 （1）湿热蕴肠证： 主症： 腹痛，腹泻，便下黏液脓血； 里急后重，肛门灼热。次症： 身热； 小便短赤； 口干口 苦；口臭。舌脉：舌质红，苔黄腻，脉滑数。 （ 2）热 毒炽盛证：主症：便下脓血或血便，量多次频；发热。次症： 里急后重； 腹胀； 口渴； 烦躁不安； 腹痛明显。 舌脉：舌质红，苔黄燥，脉滑数。 （ 3）浊毒内蕴证： 主症： 大便脓血并重； 里急后重，大便黏腻、排便不爽。 次症：口干口苦、口黏；头身困重；面色秽滞；小便短 赤不利；腹痛。舌脉：舌质红，苔黄腻，脉弦滑。 （ 4） 脾虚湿蕴证： 主症： 腹泻，夹有不消化食物； 黏液脓 血便，白多赤少，或为白冻。次症： 肢体倦怠，神疲 懒言；腹部隐痛；脘腹胀满；食少纳差。舌脉：舌质淡 红，边有齿痕，苔白腻，脉细弱或细滑。 （ 5）寒热错 杂证： 主症： 下痢稀薄，夹有黏冻； 反复发作次症： 四肢不温；腹部灼热；腹痛绵绵；口渴不欲饮。舌脉： 舌质红或淡红，苔薄黄，脉弦或细弦。 （ 6）肝郁脾 虚证：主症：常因情志因素诱发大便次数增多；大便 稀烂或黏液便；腹痛即泻，泻后痛减。次症：排便不 爽； 饮食减少； 腹胀； 肠鸣。舌脉： 舌质淡红，苔薄白， 脉弦或弦细。 （ 7）瘀阻肠络证：主症： 腹痛拒按，痛 有定处；下利脓血、血色暗红或夹有血块。次症：面 色晦暗； 腹部有痞块； 胸胁胀痛； 肌肤甲错； 泻下不爽。 舌脉： 舌质暗红，有瘀点瘀斑，脉涩或弦。 （ 8）脾肾 阳虚证： 主症： 久泻不止，大便稀薄； 夹有白冻，或 伴有完谷不化， 甚则滑脱不禁。次症： 腹胀； 食少纳差； 腹痛喜温喜按； 形寒肢冷； 腰酸膝软。舌脉： 舌质淡胖， 或有齿痕，苔薄白润，脉沉细。注： 以上 8个证候的 确定，凡具备主症 2项，加次症 2项即可诊断，舌脉\\n---\\nrecall slice 4:\\n病变部位于右半结肠 或病变范围较广者，推荐使用经内镜肠道置管术 [37] （transendoscopic enteral tubing ， TET）进行中药汤 剂或中西医结合保留灌肠（专家共识，弱推荐） 。结 肠TET操作方法： （ 1）患者左侧卧位，静脉麻醉或 清醒状态； （ 2）医生进镜至回盲部，沿活检孔插入 TET导 管 ；（ 3）植入导管至回盲部，植入长度在成人 约85 cm；（ 4）经内镜下送入组织夹将 TET管的绳圈 固定到肠皱襞，依据保留时长的需求选择组织夹的数 量，1~4枚，多为 2~3枚可满足 1~2周保留置管需求； （5）退镜后拔出管内导丝； （ 6）妥善固定 TET管体 外段于左侧臀部； （ 7）将粪菌悬液或灌肠药物溶液通 过TET注入肠道深部； （ 8）TET管可自然脱落，也 可在治疗结束后手动拔除。 对于中西药物不耐受、无效或难治的患者可以尝 试粪菌移植疗法（ fecal microbiota transplantation ， FMT）[38-40 ]（高，弱推荐） ，或骶神经刺激疗法[41] （低，弱推荐） ，或选择性白细胞吸附疗法[42]（高， 弱推荐） 。 （ 1）FMT 是一种新兴疗法，目前已经证明 FMT治疗 UC的长期疗效和安全性，但目前 FMT尚 未广泛应用，对于中西药物过敏、无效或难治的患者图1 UC病证结合诊断流程血常规、粪便常规 +潜血 +便培养， 肠镜 +病理检查、ESR、CRP 腹痛、腹泻，黏液脓血便 进一步检查 除外其他疾病相应治疗 辨 证 分 型确 诊 U C湿热蕴肠证 寒热错杂证浊毒内蕴证 瘀阻肠络证肝郁脾虚证脾虚湿蕴证热毒炽盛证初发型 活动期慢性复发型 缓解期 脾肾阳虚证临床类型 病情分期直肠型 左半结肠型 广泛结肠型病变范围 轻度 中度 重度严重程度分级\\n---\\nrecall slice 5:\\n3. 随访 应重视对本病癌变的监测， 按病情定期进行肠 镜检查[25]，若 为 直 肠 型 ，无 需 肠 镜 监 测 ，广 泛 性 结 肠 炎 或 左 半 结肠炎患者， 从最初症状出现后的第8年起， 每1-2年 （高风险 者 ） 或者每3-4年 （ 低风险者 ） 行肠镜检查。 风险评判主要依据 4条： 全结肠炎、 内镜下和/或病理组织学的炎性反应 （糜烂、 溃 疡/基底浆细胞增多， 重度、 弥漫性黏膜全层和固有层细胞增 加 ） 、 假息肉、 结直肠癌家族史。 低风险者具备0-2条， 高风险 者具备3-4条。 伴有原发性硬化性胆管炎的患者发生结肠癌风 险较高， 应每年进行肠镜监测。 对高度疑为癌变及确诊为癌变 者及 时 行 手术 治 疗\\n---\\nrecall slice 6:\\n3.3. 脾虚湿蕴型 \\n脾虚在 UC发病及病变过程中起重要作用 ，并贯穿于本病的始终 ，脾虚是 UC复发之根本 ，因此健\\n脾补肾、调和气血是本病维持缓解、防止复发的首要治法，同时兼以清肠化湿[4]。其主要临床表现为下\\n利黏液血便、白多赤少，大便溏薄，腹胀，少气懒言，易疲劳，舌淡边有齿痕。治法以益气健脾、化湿\\n和中，以参苓白术散 (《太平惠民和剂局方》 )为主方，方中以四君子汤( 党参、白术、茯苓、甘草) 平补脾\\n胃之气为君，加入和胃理气渗湿之品如扁豆、苡仁、山药、莲子，既可健脾，又能渗湿止泻，标本兼顾，\\n佐以砂仁芳香醒脾，助四君促进中焦运化，畅通气机。大便白冻黏液较多者，加\\n","content_type":"text"},{"role":"assistant","type":"answer","content":"```json\\n[\\n{\\n\\"症状简介\\":\\"患者出现反复黏液脓血便，伴随腹痛、腹泻，肠镜检查显示黏膜充血，点片状糜烂，血管网模糊，符合溃疡性结肠炎的表现。近期症状为排稀软便，便中带有大量黏液及少量脓血，血色鲜红，伴有腹泻、里急后重，便前腹痛，偶有左下腹胀满不适，肠鸣音亢进，失眠多梦，情绪不佳，时有口干口苦。\\",\\n\\"推断理由\\":\\"患者的主症包括反复黏液脓血便、腹痛、腹泻、里急后重，次症包括左下腹胀满不适、肠鸣音亢进、失眠多梦、情绪不佳、口干口苦，舌红苔黄腻，脉弦细。根据中医辨证分型，主症和次症结合舌脉表现，可推断为大肠湿热证和肝郁脾虚证。\\",\\n\\"推断症型\\":\\"1=大肠湿热，6=肝郁脾虚\\"\\n},\\n{\\n\\"症状简介\\":\\"患者有反复黏液脓血便，腹痛、腹泻，肠镜检查符合溃疡性结肠炎，近期症状包括排稀软便，便中带有大量黏液及少量脓血，血色鲜红，伴有腹泻、里急后重，便前腹痛，左下腹胀满不适，肠鸣音亢进，失眠多梦，情绪不佳，口干口苦。\\",\\n\\"推断理由\\":\\"患者的症状与热毒炽盛证的主症和次症相符，如便下脓血或血便，量多次频；腹痛明显；发热。次症包括里急后重；腹胀；口渴；烦躁不安。舌脉表现为舌质红，苔黄燥，脉滑数。虽然患者未明确描述发热症状，但其他症状与热毒炽盛证相符合。\\",\\n\\"推断症型\\":\\"2=热毒炽盛\\"\\n}\\n]\\n```","content_type":"text"},{"role":"assistant","type":"verbose","content":"{\\"msg_type\\":\\"generate_answer_finish\\",\\"data\\":\\"\\"}","content_type":"text"}],"conversation_id":"6af953b4-865a-48cd-a24b-f7098f0e156d","code":0,"msg":"success"}'
                logging.info(f"query_data: {query_data}, conversation_id: {conversation_id}, response: {response}")
                raw_output_data = parse_response(response, stream)
                output_data = parse_raw_data(raw_output_data)
                output_data[col_name[0]] = row[col_name[0]]
                if out_data is None:
                    out_data = output_data
                else:
                    out_data = pd.concat([out_data, output_data], ignore_index=True)
                logging.info(f"data to writed: {output_data}")
            
            output_excel_data(args.out_file, sheet_name, out_data, mode=args.mode)
            break
        except Exception as e:
            logging.error(f"error: {e}")
            logging.error(f"error: {traceback.format_exc()}")
            retry_times -= 1
            continue


