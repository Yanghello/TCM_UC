from sklearn.metrics import accuracy_score
import pandas as pd
def cal_acc(y_true, y_pred):
    return accuracy_score(y_true, y_pred)


file = r"./验证集与专家答案.xlsx"
fl = pd.read_excel(file)

y_true = fl["Unnamed: 2"].values.tolist()
y_pred = fl["证型(填1-7)"].values.tolist()



file = r"./验证数据集-gpt4-more_reference.xlsx"
fl = pd.read_excel(file)

y_true = fl["真实症型"].values.tolist()
y_pred_ = fl["GPT-4-Turbo"].values.tolist()
y_pred_ai = [int(i[:1]) for i in y_pred_]

diff_list = []
for i in range(len(y_true)):
    if y_true[i] == y_pred[i] and y_true[i] != y_pred_ai[i]:
        diff_list.append(i+1)

print("People correct， AI error list:", diff_list)