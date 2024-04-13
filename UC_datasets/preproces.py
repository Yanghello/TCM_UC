import jieba
import sys
import math
import pandas as pd
import json
from sklearn import model_selection

raw_file = r"./all_data.xlsx"
# get samples
fl = pd.read_excel(raw_file)

feature_name = "医案文本"
label_name = "证型"
train_file = r"./train.txt"
test_file = r"./test.txt"
dev_file = r"./dev.txt"
label_file = r"./labels.txt"
train_excel = r"./train.xlsx"
test_excel = r"./test.xlsx"

exclude_label = []

fl.rename(columns={fl.columns[2]: label_name},inplace=True)

# drop nan line
nan_indexes = []
for i in range(len(fl)):
    # is nan
    if fl.loc[i][feature_name] != fl.loc[i][feature_name]:
        nan_indexes.append(i)
fl = fl.drop(nan_indexes)

print(f"len of samples: {len(fl)}")


# remove label cannot be format as integer
invalid_label_sample = []
for i in range(len(fl)):
    label = fl.loc[i][label_name]
    if not isinstance(label, int):
        invalid_label_sample.append(i)

fl = fl.drop(invalid_label_sample)
print(f"len of samples: {len(fl)}")

print("label description: ", fl[label_name].value_counts())
# split samples
label_ = fl[label_name].values.tolist()
label_set = set()
label = []
for l in label_:
    l_str = str(l)
    i = l_str.find("+")
    if i != -1:
        l = l_str[:i]
    else:
        l = l_str
    l = int(l)
    label.append(l)
    if l not in label_set:
        label_set.add(l)
train_, test_, train_y, test_y = model_selection.train_test_split(fl[feature_name].values.tolist(), label, test_size=0.2, random_state=1024)

df_train_ = pd.DataFrame({feature_name: train_, label_name: train_y})
df_train_.to_excel(train_excel, index=False)

df_test_ = pd.DataFrame({feature_name: test_, label_name: test_y})
df_test_.to_excel(test_excel, index=False)

# with open(train_excel, "w") as f:
#     for s,l in zip(train_, train_y):
#         f.write(f'"{s}"\t{l}\n')

# with open(test_excel, "w") as f:
#     for s,l in zip(test_, test_y):
#         f.write(f'"{s}"\t{l}\n')

def feature_func(feture_line):
    feature_str_list = jieba.lcut(feture_line)
    feature = " ".join(feature_str_list)
    return feature

# fl[feature_name]  = fl[feature_name].apply(feature_func)

train = [feature_func(s) for s in train_]
test = [feature_func(s) for s in test_]

# save train test file
f_train = open(train_file, "w", encoding="utf-8")

for i in range(len(train)):
    if train_y[i] in exclude_label:
        train_y[i] = "other"
    sample = {"words": train[i], "label": f"label_{train_y[i]}"}
    # sample = {"words": train[i], "label": f"label_{ 0 if train_y[i] == 1 else 1}"}
    f_train.write(json.dumps(sample, ensure_ascii=False) + "\n")


f_test = open(test_file, "w", encoding="utf-8")
for i in range(len(test)):
    if test_y[i] in exclude_label:
        test_y[i] = "other"
    sample = {"words": test[i], "label": f"label_{test_y[i]}"}
    # sample = {"words": test[i], "label": f"label_{ 0 if test_y[i] == 1 else 1}"}
    f_test.write(json.dumps(sample, ensure_ascii=False) + "\n")

f_dev = open(dev_file, "w", encoding="utf-8")
for i in range(len(test)):
    if test_y[i] in exclude_label:
        test_y[i] = "other"
    sample = {"words": test[i], "label": f"label_{test_y[i]}"}
    # sample = {"words": test[i], "label": f"label_{ 0 if test_y[i] == 1 else 1}"}
    f_dev.write(json.dumps(sample, ensure_ascii=False) + "\n")

# write label
f_label = open(label_file, "w")

write_other = False
for label in label_set:
    if label in exclude_label:
        label = "other"
        if write_other:
            continue
        write_other = True
    f_label.write(f"label_{label}\n")
# f_label.write(f"label_0\nlabel_1\n")




