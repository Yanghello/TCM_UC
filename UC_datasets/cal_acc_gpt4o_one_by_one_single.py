import pandas as pd
from sklearn.metrics import accuracy_score, log_loss, classification_report, confusion_matrix
import re
import sys

if len(sys.argv) != 2:
    threshold = -1
else:
    threshold = float(sys.argv[1])
def cal_acc(y_true, y_pred):
    print("classification_report:\n", classification_report(y_true, y_pred))
    print("confusion_matrix:\n", confusion_matrix(y_true, y_pred))
    return accuracy_score(y_true, y_pred)

input_file = "./验证数据集-逐个输出(单症型)_gpt4o.xlsx"
data = pd.read_excel(input_file, sheet_name="Sheet1")

labels = set(["1=大肠湿热","2=热毒炽盛","3=脾虚湿蕴","4=寒热错杂","5=瘀阻肠络","6=肝郁脾虚","7=脾肾阳虚"])

file = r"./验证数据集-gpt4-more_reference.xlsx"
fl = pd.read_excel(file)

y_true = fl["真实症型"].values.tolist()

def correct(label):
    if label in labels:
        return label
    if label == '3=浊毒内蕴' or label == "3=浊毒内蕴证":
        return "1=大肠湿热"
    elif label == '7=阴血亏虚' or label == "7=阴血亏虚证":
        return "7=脾肾阳虚"
    elif label == '8=脾肾阳虚':
        return "7=脾肾阳虚"
    elif label == "6=脾肾阳虚":
        return "7=脾肾阳虚"
    elif label == "5=肝郁脾虚":
        return "6=肝郁脾虚"
    elif label == "6=肝郁脾虚证":
        return "6=肝郁脾虚"
    elif label == "8=脾肾阳虚证":
        return "7=脾肾阳虚"
    elif label == "1=湿热蕴肠":
        return "1=大肠湿热"
    elif label == "1":
        return "1=大肠湿热"
    elif label in set(["1", "2", "3", "4", "5", "6", "7"]):
        return label
    else:
        raise Exception(f"err_label: {label}")
        
y_pred_ = data["推断症型"]
confidence = data["置信度"]
y_pred_str = []
y_pred = []
label_count = 0
label_count_raw = 0
c = re.compile('[0-9]+')
y_true_filter = []
for i in range(len(y_pred_)):
    if float(confidence[i].split(",")[-1]) < threshold:
        continue
    y_ = re.split("[,，/]+",y_pred_[i])
    y = []
    for y_i in y_:
        if y_i is not None and y_i != '':
            y.append(correct(y_i.strip()))
            break
    label_count_raw += len(y)
    label_count += len(set(y))
    y_str = ",".join(y)
    y_pred_str.append(y_str)
    y_all = c.findall(y_str)
    assert len(y_all) == 1
    y_all = [int(d) for d in y_all]
    if y_true[i] in set(y_all):
        y_pred.append(y_true[i])
    else:
        y_pred.append(y_all[0])
    y_true_filter.append(y_true[i])

print("raw label count", label_count_raw)
print("acc[gpt4-逐个输出（单症型）]:", cal_acc(y_true_filter, y_pred))
print("total label count", label_count, ", average count per sample: ", label_count/len(y_pred_))

data["推断症型"] = y_pred_str
data.to_excel("./验证数据集-gpt4o-逐个输出(单症型)_corrected.xlsx", index=False)


