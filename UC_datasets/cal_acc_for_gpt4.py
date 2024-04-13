from sklearn.metrics import accuracy_score
import pandas as pd
import re

def cal_acc(y_true, y_pred):
    return accuracy_score(y_true, y_pred)


file = r"./验证数据集-gpt4-more_reference.xlsx"
fl = pd.read_excel(file)

y_true = fl["真实症型"].values.tolist()
y_pred_ = fl["GPT-4-Turbo"].values.tolist()
y_pred = [int(i[:1]) for i in y_pred_]

print("acc[GPT-4-Turbo]:", cal_acc(y_true, y_pred))


y_pred_ = fl["GPT-4 with more reference"].values.tolist()
y_pred = [int(i[:1]) for i in y_pred_]
print("acc[GPT-4-more-reference]:", cal_acc(y_true, y_pred))


# two label
y_pred_ = fl["GPT-4 two ans"].values.tolist()
c = re.compile('[0-9]+')

y_pred = []
for id, i in enumerate(y_pred_):
    y_all = c.findall(i)
    assert len(y_all) > 0
    y_all = [int(d) for d in y_all]
    if y_true[id] in set(y_all):
        y_pred.append(y_true[id])
    else:
        y_pred.append(y_all[0])
print("acc[GPT-4-two-ans]:", cal_acc(y_true, y_pred))

# multi label
y_pred_ = fl["GPT-4 mult"].values.tolist()
c = re.compile('[0-9]+')

y_pred = []
for id, i in enumerate(y_pred_):
    y_all = c.findall(str(i))
    assert len(y_all) > 0
    y_all = [int(d) for d in y_all]
    if y_true[id] in set(y_all):
        y_pred.append(y_true[id])
    else:
        y_pred.append(y_all[0])
print("acc[GPT-4-multi-ans]:", cal_acc(y_true, y_pred))

# kimi 
y_pred_ = fl["kimi"].values.tolist()
y_pred = [int(i) for i in y_pred_]

print("acc [kimi]:", cal_acc(y_true, y_pred))

# # kimi multi
# y_pred_ = fl["kimi-multi"].values.tolist()
# c = re.compile('[0-9]+')

# y_pred = []
# for id, i in enumerate(y_pred_):
#     y_all = c.findall(i)
#     assert len(y_all) > 0
#     y_all = [int(d) for d in y_all]
#     if y_true[id] in set(y_all):
#         y_pred.append(y_true[id])
#     else:
#         y_pred.append(y_all[0])
# print("acc[kimi-multi]:", cal_acc(y_true, y_pred))
