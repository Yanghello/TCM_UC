from sklearn.metrics import accuracy_score, log_loss, classification_report, confusion_matrix
import pandas as pd
def cal_acc(y_true, y_pred):
    print("classification_report:\n", classification_report(y_true, y_pred))
    print("confusion_matrix:\n", confusion_matrix(y_true, y_pred))
    return accuracy_score(y_true, y_pred)


file = r"./验证集与专家答案.xlsx"
fl = pd.read_excel(file)

y_true = fl["Unnamed: 2"].values.tolist()
y_pred = fl["证型(填1-7)"].values.tolist()

print(cal_acc(y_true, y_pred))