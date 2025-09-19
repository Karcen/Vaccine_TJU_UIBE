import os
import time
import base64
import pandas as pd
from volcenginesdkarkruntime import Ark

# 配置参数
FOLDER_PATH = ".\test"
OUTPUT_EXCEL = ".\test\rider_orders.xlsx"
MODEL = "doubao-1.5-vision-pro-250328"
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
VALID_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".bmp")
API_CALL_DELAY = 3  # 调用间隔3秒
API_KEY = "YOUR_API"


def is_valid_image(file_path):
    """验证图片有效性"""
    if not file_path.lower().endswith(VALID_IMAGE_EXT):
        return False, "非图片格式"
    file_size = os.path.getsize(file_path)
    if file_size > MAX_IMAGE_SIZE:
        return False, f"图片过大（{file_size / 1024 / 1024:.1f}MB）"
    try:
        with open(file_path, "rb") as f:
            f.read(100)
        return True, "有效"
    except Exception as e:
        return False, f"文件损坏：{str(e)[:20]}"


def image_to_base64(file_path):
    """图片转Base64编码"""
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".bmp": "image/bmp"}
    with open(file_path, "rb") as f:
        b64_str = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_map[ext]};base64,{b64_str}"


def extract_orders_data(client, image_b64, filename):
    """调用模型提取今日完成单数和总完成单数"""
    prompt = f"""
    任务：从提供的骑手相关图片中提取"今日完成单数"和"总完成单数"数据。

    具体要求：
    1. 识别"今日完成单数"相关信息（包括但不限于以下表述）：
       - "今日完成"及数字
       - "今日完成单量"及数值
       - "今日已完成"及对应数字
       - "今日完成订单"及数量

    2. 识别"总完成单数"相关信息（包括但不限于以下表述）：
       - "总完成"及数字
       - "累计完成"及数值
       - "历史完成"及对应数字
       - "总完成订单"及数量
       - "累计订单"及数量

    3. 提取规则（适用于两个字段）：
       - 若能清晰识别具体数字，直接返回该数字
       - 若数字模糊或部分被遮挡，返回"模糊"
       - 若明确显示为0，返回"0"
       - 若存在相关字段但无具体数值，返回"无数据"
       - 若未找到该字段，返回"未找到"

    4. 输出格式（严格遵守）：
       仅返回"文件名,今日完成单数,总完成单数"格式，无其他内容
       示例：
       {filename},35,1250
       {filename},模糊,890
       {filename},5,未找到
       {filename},未找到,未找到

    请严格按照上述格式输出，不要添加任何解释、说明或额外字符！
    """

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt.strip()},
                {"type": "image_url", "image_url": {"url": image_b64}}
            ]}],
            response_format={"type": "text"},
            timeout=15
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"调用错误: {str(e)[:30]}"


def process_images():
    """批量处理主函数"""
    client = Ark(api_key=API_KEY)
    results = []
    all_files = os.listdir(FOLDER_PATH)
    total = len(all_files)
    print(f"开始处理（共{total}个文件）\n")

    for i, filename in enumerate(all_files, 1):
        file_path = os.path.join(FOLDER_PATH, filename)
        print(f"处理中（{i}/{total}）：{filename}")

        # 校验图片
        is_valid, msg = is_valid_image(file_path)
        if not is_valid:
            print(f"  → 跳过：{msg}\n")
            results.append([filename, "", "", msg])
            continue

        # 转Base64
        try:
            image_b64 = image_to_base64(file_path)
        except Exception as e:
            err = f"编码失败：{str(e)[:20]}"
            print(f"  → {err}\n")
            results.append([filename, "", "", err])
            continue

        # 控制调用频率
        if i > 1:
            time.sleep(API_CALL_DELAY)

        # 调用模型
        raw_result = extract_orders_data(client, image_b64, filename)
        print(f"  → 模型原始返回：{raw_result[:100]}")  # 打印原始结果用于调试

        # 解析结果
        if raw_result.startswith("调用错误"):
            print(f"  → 调用错误\n")
            results.append([filename, "", "", raw_result])
        else:
            # 分割结果（最多分割两次，确保正确提取两个数值）
            parts = [p.strip() for p in raw_result.split(",", 2)]

            if len(parts) == 3 and (filename in parts[0] or parts[0] in filename):
                # 完美匹配格式
                today, total = parts[1], parts[2]
                print(f"  → 结果：今日完成单数={today}，总完成单数={total}\n")
                results.append([filename, today, total, "成功识别"])
            elif len(parts) >= 2:
                # 部分匹配，尝试提取可用数据
                print(f"  → 结果：格式不完整，尝试提取\n")
                today = parts[1] if len(parts) > 1 else ""
                total = parts[2] if len(parts) > 2 else ""
                results.append([filename, today, total, f"格式不完整: {raw_result[:50]}"])
            else:
                # 无法解析，记录原始结果
                print(f"  → 结果：无法解析\n")
                results.append([filename, "", "", f"无法解析: {raw_result[:50]}"])

    # 保存结果
    df = pd.DataFrame(results, columns=["文件名", "今日完成单数", "总完成单数", "备注"])
    df.to_excel(OUTPUT_EXCEL, index=False)
    print(f"处理完成！结果文件：{os.path.abspath(OUTPUT_EXCEL)}")


if __name__ == "__main__":
    if not os.path.exists(FOLDER_PATH):
        raise FileNotFoundError(f"文件夹不存在：{FOLDER_PATH}")
    process_images()
