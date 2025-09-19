import os
from volcenginesdkarkruntime import Ark

# 方法1：直接使用API密钥
client = Ark(api_key="bd1752bf-0c82-46ba-9c6a-53e2f613f105")

# 方法2：使用环境变量（推荐）
# client = Ark(api_key=os.environ.get("VOLC_API_KEY"))

completion = client.chat.completions.create(
    model="doubao-seed-1-6-vision-250815",
    messages=[
        {"role": "user", "content": "You are a helpful assistant."}
    ]
)
print(completion.choices[0].message)