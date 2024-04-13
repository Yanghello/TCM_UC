import pandas as pd

all_files = ["万方 数据库 .xlsx", "维普数据库.xlsx", "知网-数据库.xlsx"]

df = None

for file in all_files:
    df_ = pd.read_excel(file)
    # print(f"data shape of file {file}: ", df_.shape)
    # df_ = df_.dropna()
    print(f"data shape of file {file}: ", df_.shape)
    if df is None:
        df = df_
    else:
        df = pd.concat([df, df_])

# shuffle dataframe'
df = df.sample(frac=1)
print("data shape: ", df.shape)

df.to_excel("all_data.xlsx", index=False)