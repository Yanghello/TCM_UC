from sklearn.metrics import accuracy_score
import pandas as pd
def cal_acc(y_true, y_pred):
    return accuracy_score(y_true, y_pred)


file = r"./验证集与专家答案.xlsx"
fl = pd.read_excel(file)

y_true = fl["Unnamed: 2"].values.tolist()
y_pred = fl["证型(填1-7)"].values.tolist()

print(cal_acc(y_true, y_pred))