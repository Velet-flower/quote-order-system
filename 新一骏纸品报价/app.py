# -*- coding: utf-8 -*-
"""
新一骏纸品有限公司 - 智能报价系统
Flask 单文件应用：纸箱厂智能报价与数据管理
启动命令：python app.py
"""

import json
import os
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, jsonify

app = Flask(__name__)

# ============================================================
#  数据存储路径
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_FILE = os.path.join(BASE_DIR, 'rules.json')        # 材质数据
QUOTES_FILE = os.path.join(BASE_DIR, 'quotations.json')   # 报价记录
CUSTOMERS_FILE = os.path.join(BASE_DIR, 'customers.json') # 客户数据


# ============================================================
#  通用 JSON 读写
# ============================================================
def load_json(filepath, default):
    """读取 JSON，文件不存在则自动创建。"""
    if not os.path.exists(filepath):
        save_json(filepath, default)
        return [] if isinstance(default, list) else default
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


def save_json(filepath, data):
    """保存 JSON。"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_rules():
    """读取材质数据，自动补齐 discounts 字段（兼容旧数据）。"""
    rules = load_json(RULES_FILE, [])
    for r in rules:
        if 'discounts' not in r or not isinstance(r['discounts'], list):
            r['discounts'] = []
    return rules


def save_rules(rules):
    save_json(RULES_FILE, rules)


def load_quotes():
    return load_json(QUOTES_FILE, [])


def save_quotes(quotes):
    save_json(QUOTES_FILE, quotes)


def load_customers():
    return load_json(CUSTOMERS_FILE, [])


def save_customers(customers):
    save_json(CUSTOMERS_FILE, customers)


def get_next_id(items):
    if not items:
        return 1
    return max(item['id'] for item in items) + 1


def generate_quote_no(quotes):
    """生成报价单编号：QJ + YYYYMMDD + 3位当日序号，如 QJ20260731001"""
    today_str = datetime.now().strftime('%Y%m%d')
    prefix = f'QJ{today_str}'
    # 统计今天已有的报价单数量
    today_count = sum(1 for q in quotes if q.get('quote_no', '').startswith(prefix))
    seq = today_count + 1
    return f'{prefix}{seq:03d}'


def backfill_quote_no(quotes):
    """为已有报价记录补充编号（按创建时间顺序）"""
    changed = False
    for q in quotes:
        if not q.get('quote_no'):
            # 从 created_at 提取日期，没有则用今天
            created = q.get('created_at', '')
            if len(created) >= 10:
                date_str = created[:10].replace('-', '')
            else:
                date_str = datetime.now().strftime('%Y%m%d')
            prefix = f'QJ{date_str}'
            # 统计同日期已有编号数
            same_day = sum(1 for x in quotes if x.get('quote_no', '').startswith(prefix))
            q['quote_no'] = f'{prefix}{same_day + 1:03d}'
            changed = True
    return changed


# ============================================================
#  辅助函数
# ============================================================
def format_discount(rate):
    """折扣率转中文显示：0.95→95折，0.9→9折，0.88→88折。"""
    pct = rate * 100
    if pct % 10 == 0:
        return f"{int(pct // 10)}折"
    return f"{int(pct)}折"


def format_discounts(discounts):
    """优惠档位列表转文本。"""
    if not discounts:
        return '—'
    parts = []
    for d in sorted(discounts, key=lambda x: x['min_qty']):
        parts.append(f"≥{d['min_qty']} {format_discount(d['discount_rate'])}")
    return '，'.join(parts)


# ============================================================
#  公共样式 — 商务精致风格
# ============================================================
BASE_CSS = """
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Microsoft YaHei", "PingFang SC", "Heiti SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background-color: #FDF5E6;
    background-image:
      radial-gradient(circle at 12% 18%, rgba(139,90,43,0.07), transparent 45%),
      radial-gradient(circle at 88% 82%, rgba(139,90,43,0.07), transparent 45%);
    color: #3a2a1a;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    -webkit-font-smoothing: antialiased;
  }

  /* ===== 顶部品牌栏 ===== */
  .header {
    background: rgba(139,90,43,0.92);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    color: #FDF5E6;
    padding: 24px 0 22px;
    text-align: center;
    border-bottom: 3px solid rgba(107,68,35,0.5);
    box-shadow: 0 2px 14px rgba(139,90,43,0.25);
  }
  .header h1 {
    font-size: 26px;
    font-weight: 600;
    letter-spacing: 2px;
    color: #FDF5E6;
  }
  .header h1 .accent { color: #F5DEB3; }
  .header p {
    margin-top: 7px;
    font-size: 13px;
    color: rgba(253,245,230,0.72);
    letter-spacing: 1px;
  }

  /* ===== 导航栏 ===== */
  .nav {
    background: rgba(107,68,35,0.88);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    padding: 0;
    text-align: center;
    display: flex;
    justify-content: center;
    gap: 0;
    box-shadow: 0 1px 6px rgba(0,0,0,0.1);
  }
  .nav a {
    color: rgba(253,245,230,0.72);
    text-decoration: none;
    padding: 13px 28px;
    font-size: 14px;
    transition: all 0.25s ease;
    border-bottom: 2px solid transparent;
    letter-spacing: 0.5px;
  }
  .nav a:hover {
    color: #FDF5E6;
    background: rgba(255,255,255,0.07);
  }
  .nav a.active {
    color: #FDF5E6;
    border-bottom: 2px solid #D4A88B;
    background: rgba(255,255,255,0.06);
  }

  /* ===== 主容器 ===== */
  .container {
    max-width: 960px;
    margin: 32px auto;
    flex: 1;
    width: 92%;
  }

  /* ===== 底部 ===== */
  .footer {
    background: rgba(139,90,43,0.92);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    color: rgba(253,245,230,0.6);
    text-align: center;
    padding: 16px 0;
    margin-top: auto;
    font-size: 12px;
    letter-spacing: 0.5px;
    border-top: 1px solid rgba(107,68,35,0.4);
  }

  /* ===== 卡片 — 毛玻璃磨砂 ===== */
  .card {
    background: rgba(255,255,255,0.75);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(139,90,43,0.14);
    border-radius: 16px;
    padding: 32px 34px;
    margin-bottom: 22px;
    box-shadow: 0 8px 32px rgba(139,90,43,0.12), 0 2px 8px rgba(0,0,0,0.04);
  }
  .card h2 {
    color: #8B5A2B;
    border-bottom: 1px solid rgba(139,90,43,0.14);
    padding-bottom: 14px;
    margin-bottom: 26px;
    font-size: 19px;
    font-weight: 600;
    position: relative;
  }
  .card h2::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    width: 50px;
    height: 2px;
    background: #8B5A2B;
  }

  /* ===== 表单标签 ===== */
  label {
    display: block;
    margin-bottom: 7px;
    color: #6B4423;
    font-weight: 500;
    font-size: 13px;
    letter-spacing: 0.3px;
  }

  /* ===== 输入框 — 圆润 + 棕色聚焦 ===== */
  input[type="text"], input[type="number"], select {
    width: 100%;
    padding: 11px 14px;
    border: 1.5px solid rgba(139,90,43,0.2);
    border-radius: 10px;
    font-size: 14px;
    margin-bottom: 18px;
    background: rgba(255,255,255,0.6);
    color: #3a2a1a;
    transition: border-color 0.25s, box-shadow 0.25s, background 0.25s;
  }
  input::placeholder, textarea::placeholder { color: #C4A882; }
  input:focus, select:focus {
    outline: none;
    border-color: #8B5A2B;
    box-shadow: 0 0 0 3px rgba(139,90,43,0.15);
    background: rgba(255,255,255,0.9);
  }
  select {
    cursor: pointer;
    -webkit-appearance: none;
    -moz-appearance: none;
    appearance: none;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'><path fill='%238B5A2B' d='M6 8L0 0h12z'/></svg>");
    background-repeat: no-repeat;
    background-position: right 14px center;
    padding-right: 36px;
  }
  textarea {
    width: 100%;
    padding: 11px 14px;
    border: 1.5px solid rgba(139,90,43,0.2);
    border-radius: 10px;
    font-size: 14px;
    margin-bottom: 18px;
    background: rgba(255,255,255,0.6);
    color: #3a2a1a;
    resize: vertical;
    min-height: 72px;
    font-family: inherit;
    transition: border-color 0.25s, box-shadow 0.25s, background 0.25s;
  }
  textarea:focus {
    outline: none;
    border-color: #8B5A2B;
    box-shadow: 0 0 0 3px rgba(139,90,43,0.15);
    background: rgba(255,255,255,0.9);
  }

  /* ===== 按钮 — 牛皮纸棕 + 悬停上浮 ===== */
  .btn {
    background: #8B5A2B;
    color: #FDF5E6;
    border: none;
    padding: 12px 40px;
    font-size: 15px;
    border-radius: 10px;
    cursor: pointer;
    transition: background 0.3s, transform 0.3s, box-shadow 0.3s;
    font-weight: 600;
    letter-spacing: 1px;
    margin-top: 4px;
    box-shadow: 0 4px 12px rgba(139,90,43,0.28);
  }
  .btn:hover {
    background: #6B4423;
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(139,90,43,0.38);
  }
  .btn:active {
    transform: translateY(0);
    box-shadow: 0 2px 8px rgba(139,90,43,0.2);
  }

  /* ===== 成功提示 ===== */
  .success-msg {
    background: rgba(212,237,212,0.8);
    color: #1d7a3e;
    border: 1px solid rgba(45,164,78,0.3);
    border-left: 3px solid #2da44e;
    padding: 14px 18px;
    border-radius: 8px;
    margin-bottom: 22px;
    font-size: 15px;
    text-align: center;
    font-weight: 500;
  }
  .form-row {
    display: flex;
    gap: 18px;
    margin-bottom: 0;
  }
  .form-group { flex: 1; }

  /* ===== 优惠档位录入区 ===== */
  .discount-section {
    background: rgba(139,90,43,0.05);
    border: 1px solid rgba(139,90,43,0.12);
    border-radius: 10px;
    padding: 16px 18px 8px;
    margin-bottom: 18px;
  }
  .discount-section > label {
    margin-bottom: 12px;
    color: #6B4423;
  }
  .discount-row {
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
    align-items: center;
  }
  .discount-row input {
    margin-bottom: 0 !important;
    flex: 1;
  }
  .btn-del-row {
    background: rgba(192,57,43,0.1);
    color: #c0392b;
    border: 1px solid rgba(192,57,43,0.2);
    width: 38px;
    height: 40px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 15px;
    transition: background 0.2s, color 0.2s, border-color 0.2s;
    flex-shrink: 0;
    line-height: 1;
  }
  .btn-del-row:hover {
    background: #c0392b;
    color: #fff;
    border-color: #c0392b;
  }
  .btn-add-row {
    background: transparent;
    color: #8B5A2B;
    border: 1.5px dashed rgba(139,90,43,0.4);
    padding: 8px 20px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    transition: background 0.2s, border-color 0.2s;
    margin-top: 2px;
  }
  .btn-add-row:hover {
    background: rgba(139,90,43,0.08);
    border-color: #8B5A2B;
  }
  .discount-hint {
    font-size: 12px;
    color: #A0826D;
    margin-top: 4px;
    margin-bottom: 8px;
  }

  /* ===== 结果区 — 毛玻璃 ===== */
  .result-box {
    background: rgba(253,245,230,0.6);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(139,90,43,0.14);
    border-top: 3px solid #8B5A2B;
    border-radius: 12px;
    padding: 26px 30px;
    margin-top: 26px;
    box-shadow: 0 4px 16px rgba(139,90,43,0.08);
  }
  .result-box h3 {
    color: #8B5A2B;
    text-align: center;
    margin-bottom: 20px;
    font-size: 17px;
    font-weight: 600;
    letter-spacing: 1px;
  }
  .result-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 11px 0;
    border-bottom: 1px solid rgba(139,90,43,0.08);
    font-size: 14px;
  }
  .result-row:last-child { border-bottom: none; }
  .result-label {
    color: #8B7355;
    font-weight: 500;
    font-size: 13px;
  }
  .result-value {
    color: #3a2a1a;
    font-size: 15px;
    font-weight: 500;
  }

  /* ===== 折扣标签 — 红色背景突出 ===== */
  .discount-notice {
    color: #fff;
    font-size: 14px;
    font-weight: 500;
    text-align: center;
    margin: 16px 0;
    padding: 14px 16px;
    background: #c0392b;
    border: none;
    border-radius: 8px;
    line-height: 1.7;
    box-shadow: 0 3px 10px rgba(192,57,43,0.3);
  }

  /* ===== 总价 ===== */
  .total-price-label {
    text-align: center;
    color: #8B7355;
    font-size: 13px;
    margin-top: 18px;
    margin-bottom: 6px;
    letter-spacing: 1px;
  }
  .total-price {
    color: #8B5A2B;
    font-size: 34px;
    font-weight: 700;
    text-align: center;
    letter-spacing: 1px;
  }
  .total-price .yuan {
    font-size: 18px;
    font-weight: 500;
    margin-left: 4px;
    color: #6B4423;
  }

  /* ===== 备注显示 ===== */
  .remark-display {
    margin-top: 16px;
    padding: 12px 16px;
    background: rgba(139,90,43,0.06);
    border: 1px solid rgba(139,90,43,0.12);
    border-left: 3px solid #8B5A2B;
    border-radius: 8px;
    font-size: 13px;
    color: #6B4423;
    line-height: 1.6;
  }
  .remark-display .rm-label {
    color: #8B5A2B;
    font-weight: 600;
    margin-right: 6px;
  }

  /* ===== 表格 ===== */
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 16px;
    font-size: 14px;
  }
  th, td {
    border-bottom: 1px solid rgba(139,90,43,0.08);
    padding: 13px 12px;
    text-align: center;
  }
  th {
    background: rgba(139,90,43,0.08);
    color: #6B4423;
    font-weight: 600;
    font-size: 13px;
    letter-spacing: 0.3px;
    border-bottom: 2px solid rgba(139,90,43,0.15);
  }
  tbody tr {
    transition: background 0.15s;
  }
  tbody tr:hover { background: rgba(139,90,43,0.04); }
  td { color: #3a2a1a; }
  td.remark-cell {
    text-align: left;
    max-width: 200px;
    color: #8B7355;
    font-size: 13px;
  }
  td.disc-cell {
    font-size: 12px;
    color: #6B4423;
    text-align: left;
  }
  .empty-msg {
    text-align: center;
    color: #A0826D;
    padding: 48px 20px;
    font-size: 15px;
  }

  /* ===== 提示条 ===== */
  .tip {
    background: rgba(139,90,43,0.06);
    border: 1px solid rgba(139,90,43,0.1);
    border-left: 3px solid #8B5A2B;
    padding: 12px 16px;
    margin-bottom: 22px;
    color: #6B4423;
    font-size: 13px;
    border-radius: 0 8px 8px 0;
    line-height: 1.6;
  }
  .tip strong { color: #8B5A2B; }

  /* ===== 表格内操作链接 ===== */
  .btn-link-del {
    color: #c0392b;
    text-decoration: none;
    font-size: 12px;
    padding: 4px 10px;
    border: 1px solid rgba(192,57,43,0.25);
    border-radius: 5px;
    transition: background 0.2s, color 0.2s, border-color 0.2s;
  }
  .btn-link-del:hover {
    background: #c0392b;
    color: #fff;
    border-color: #c0392b;
  }
  .btn-link-edit {
    color: #8B5A2B;
    text-decoration: none;
    font-size: 12px;
    padding: 4px 10px;
    border: 1px solid rgba(139,90,43,0.25);
    border-radius: 5px;
    transition: background 0.2s, color 0.2s, border-color 0.2s;
    margin-right: 4px;
  }
  .btn-link-edit:hover {
    background: #8B5A2B;
    color: #fff;
    border-color: #8B5A2B;
  }
  .tag-none {
    display: inline-block;
    color: #C4A882;
    font-size: 12px;
  }

  /* ===== 清空全部按钮 ===== */
  .table-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 16px;
    flex-wrap: wrap;
    gap: 10px;
  }

  /* ===== 搜索栏 ===== */
  .search-bar {
    margin-bottom: 20px;
    padding: 16px 20px;
    background: rgba(139, 90, 43, 0.04);
    border: 1px solid rgba(139, 90, 43, 0.12);
    border-radius: 12px;
  }
  .search-form {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  .search-input {
    flex: 1;
    min-width: 200px;
    padding: 9px 14px;
    border: 1.5px solid #ddd;
    border-radius: 8px;
    font-size: 14px;
    background: rgba(255, 255, 255, 0.85);
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .search-input:focus {
    outline: none;
    border-color: #8B5A2B;
    box-shadow: 0 0 0 3px rgba(139, 90, 43, 0.12);
  }
  .search-date {
    padding: 9px 12px;
    border: 1.5px solid #ddd;
    border-radius: 8px;
    font-size: 13px;
    background: rgba(255, 255, 255, 0.85);
    color: #555;
    transition: border-color 0.2s;
  }
  .search-date:focus {
    outline: none;
    border-color: #8B5A2B;
  }
  .search-btn {
    padding: 9px 24px;
    background: #8B5A2B;
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    cursor: pointer;
    transition: transform 0.15s, box-shadow 0.2s;
  }
  .search-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(139, 90, 43, 0.3);
  }
  .search-reset {
    color: #8B5A2B;
    font-size: 13px;
    text-decoration: none;
    padding: 9px 12px;
    border-radius: 8px;
    transition: background 0.2s;
  }
  .search-reset:hover {
    background: rgba(139, 90, 43, 0.08);
  }
  .btn-clear-all {
    display: inline-block;
    background: transparent;
    color: #c0392b;
    border: 1.5px solid rgba(192,57,43,0.3);
    padding: 8px 22px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    text-decoration: none;
    transition: background 0.2s, color 0.2s, border-color 0.2s;
  }
  .btn-clear-all:hover {
    background: #c0392b;
    color: #fff;
    border-color: #c0392b;
  }
</style>
"""


# 优惠档位动态录入 JS
DISCOUNT_JS = """
<script>
function addDiscountRow() {
  var c = document.getElementById('discount-container');
  var row = document.createElement('div');
  row.className = 'discount-row';
  row.innerHTML =
    '<input type="number" name="discounts_min_qty[]" min="1" placeholder="数量 >=" style="flex:1">' +
    '<input type="number" name="discounts_rate[]" step="0.01" min="0.01" max="0.99" placeholder="折扣率 如 0.95" style="flex:1">' +
    '<button type="button" class="btn-del-row" onclick="removeDiscountRow(this)">\\u2715</button>';
  c.appendChild(row);
}
function removeDiscountRow(btn) {
  var rows = document.querySelectorAll('#discount-container .discount-row');
  if (rows.length > 1) {
    btn.parentNode.remove();
  } else {
    btn.parentNode.querySelectorAll('input').forEach(function(i){ i.value=''; });
  }
}
</script>
"""


def page_wrapper(title, nav_active, content, extra_head=''):
    """生成完整页面：头部 + 导航 + 内容 + 底部。"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  {BASE_CSS}
  {extra_head}
</head>
<body>
  <div class="header">
    <h1>新一骏<span class="accent">纸品</span> · 智能报价系统</h1>
    <p>纸箱智能报价 ｜ 材质数据管理 ｜ 快速精准核算</p>
  </div>
  <div class="nav">
    <a href="/" class="{'active' if nav_active == 'home' else ''}">首页报价器</a>
    <a href="/add" class="{'active' if nav_active == 'add' else ''}">添加材质</a>
    <a href="/list" class="{'active' if nav_active == 'list' else ''}">材质数据</a>
    <a href="/customers" class="{'active' if nav_active == 'customers' else ''}">客户管理</a>
    <a href="/quotes" class="{'active' if nav_active == 'quotes' else ''}">报价记录</a>
  </div>
  <div class="container">
    {content}
  </div>
  <div class="footer">
    &copy; 2026 新一骏纸品有限公司　版权所有
  </div>
</body>
</html>"""


# ============================================================
#  路由 1：首页报价器（/）
# ============================================================
@app.route('/', methods=['GET', 'POST'])
def index():
    rules = load_rules()
    customers = load_customers()
    result_html = ''
    form_data = {'length': '', 'width': '', 'height': '', 'quantity': '', 'material_id': '', 'remark': '', 'unit': 'cm', 'customer_id': ''}

    if request.method == 'POST':
        try:
            length = float(request.form.get('length', 0))
            width = float(request.form.get('width', 0))
            height = float(request.form.get('height', 0))
            quantity = int(request.form.get('quantity', 0))
            material_id = int(request.form.get('material_id', 0))
            customer_id = int(request.form.get('customer_id', 0)) if request.form.get('customer_id') else 0
            remark = request.form.get('remark', '').strip()
            unit = request.form.get('unit', 'cm')
            # 单位换算：统一转为厘米参与计算
            unit_factor = {'mm': 0.1, 'cm': 1.0, 'm': 100.0}.get(unit, 1.0)
            length_cm = length * unit_factor
            width_cm = width * unit_factor
            height_cm = height * unit_factor

            form_data = {
                'length': request.form.get('length', ''),
                'width': request.form.get('width', ''),
                'height': request.form.get('height', ''),
                'quantity': request.form.get('quantity', ''),
                'material_id': request.form.get('material_id', ''),
                'remark': remark,
                'unit': unit,
                'customer_id': request.form.get('customer_id', '')
            }

            # 查找选定材质
            material = None
            for r in rules:
                if r['id'] == material_id:
                    material = r
                    break

            # 查找选定客户
            customer_name = ''
            if customer_id:
                for c in customers:
                    if c['id'] == customer_id:
                        customer_name = c['name']
                        break

            if not material:
                result_html = '<div class="discount-notice">请选择有效的材质！</div>'
            elif not customer_id:
                result_html = '<div class="discount-notice">请先选择客户！如无客户可点击「快速新建」添加。</div>'
            elif length <= 0 or width <= 0 or quantity <= 0:
                result_html = '<div class="discount-notice">请输入有效的尺寸和数量！</div>'
            else:
                len_add = material['length_addition']
                wid_add = material['width_addition']
                unit_price = material['unit_price']

                # 核心算法公式（尺寸已换算为厘米）
                # 用料面积 = (长度 + 长度加放) × (宽度 + 宽度加放) × 2 × 数量
                area = (length_cm + len_add) * (width_cm + wid_add) * 2 * quantity

                # 原始总价 = 用料面积 × 单价
                original_total = area * unit_price

                # 优惠匹配：按材质录入的优惠规则，取数量达标的最高档
                discounts = material.get('discounts', [])
                applicable = [d for d in discounts if d['min_qty'] <= quantity]
                has_discount = False
                if applicable:
                    best = max(applicable, key=lambda d: d['min_qty'])
                    discount_rate = best['discount_rate']
                    final_total = original_total * discount_rate
                    discount_amount = original_total - final_total
                    has_discount = True
                    discount_html = f"""
                    <div class="discount-notice">
                      原始总价：{original_total:.2f} 元<br>
                      优惠档位：数量 ≥ {best['min_qty']}，享 {format_discount(discount_rate)}<br>
                      折扣金额：-{discount_amount:.2f} 元
                    </div>
                    """
                else:
                    final_total = original_total
                    discount_html = ''

                # 备注显示
                remark_html = ''
                if remark:
                    remark_html = f"""
                    <div class="remark-display">
                      <span class="rm-label">客户备注</span>{remark}
                    </div>
                    """

                # 单位换算显示（非厘米时额外显示换算结果）
                if unit != 'cm':
                    convert_row = f"""
                  <div class="result-row">
                    <span class="result-label">换算厘米</span>
                    <span class="result-value">{length_cm:.1f} × {width_cm:.1f} × {height_cm:.1f} cm</span>
                  </div>"""
                else:
                    convert_row = ''

                # 生成报价单编号
                all_quotes = load_quotes()
                quote_no = generate_quote_no(all_quotes)

                # 客户信息行
                customer_row = f"""
                  <div class="result-row">
                    <span class="result-label">客户</span>
                    <span class="result-value">{customer_name}</span>
                  </div>""" if customer_name else ''

                result_html = f"""
                <div class="result-box">
                  <h3>报价结果</h3>
                  <div class="result-row">
                    <span class="result-label">报价单号</span>
                    <span class="result-value" style="color:#8B5A2B;font-weight:600;font-size:16px;">{quote_no}</span>
                  </div>
                  {customer_row}
                  <div class="result-row">
                    <span class="result-label">选用材质</span>
                    <span class="result-value">{material['name']}</span>
                  </div>
                  <div class="result-row">
                    <span class="result-label">输入尺寸</span>
                    <span class="result-value">{length:.1f} × {width:.1f} × {height:.1f} {unit}</span>
                  </div>
                  {convert_row}
                  <div class="result-row">
                    <span class="result-label">数量</span>
                    <span class="result-value">{quantity} 个</span>
                  </div>
                  <div class="result-row">
                    <span class="result-label">长度加放值</span>
                    <span class="result-value">{len_add:.2f} cm</span>
                  </div>
                  <div class="result-row">
                    <span class="result-label">宽度加放值</span>
                    <span class="result-value">{wid_add:.2f} cm</span>
                  </div>
                  <div class="result-row">
                    <span class="result-label">用料面积</span>
                    <span class="result-value">{area:.2f} 平方厘米</span>
                  </div>
                  <div class="result-row">
                    <span class="result-label">纸质单价</span>
                    <span class="result-value">{unit_price:.6f} 元/平方厘米</span>
                  </div>
                  {discount_html}
                  <div class="total-price-label">最终应付总价</div>
                  <div class="total-price">{final_total:.2f}<span class="yuan">元</span></div>
                  {remark_html}
                </div>
                """

                # 保存报价记录
                quotes = all_quotes
                quote_record = {
                    'id': get_next_id(quotes),
                    'quote_no': quote_no,
                    'customer_id': customer_id if customer_id else None,
                    'customer_name': customer_name,
                    'material_name': material['name'],
                    'length': length,
                    'width': width,
                    'height': height,
                    'input_unit': unit,
                    'quantity': quantity,
                    'area': round(area, 2),
                    'unit_price': unit_price,
                    'original_total': round(original_total, 2),
                    'discount_rate': discount_rate if has_discount else None,
                    'discount_desc': format_discount(discount_rate) if has_discount else '',
                    'final_total': round(final_total, 2),
                    'remark': remark,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                quotes.append(quote_record)
                save_quotes(quotes)

        except (ValueError, TypeError):
            result_html = '<div class="discount-notice">请输入有效的数字！</div>'

    # 构建材质下拉菜单
    if rules:
        options_html = ''
        for r in rules:
            selected = 'selected' if str(r['id']) == str(form_data['material_id']) else ''
            disc_text = f' / {format_discounts(r.get("discounts", []))}' if r.get('discounts') else ''
            options_html += f'<option value="{r["id"]}" {selected}>{r["name"]}（长加放{r["length_addition"]}cm / 宽加放{r["width_addition"]}cm / {r["unit_price"]}元/c㎡{disc_text}）</option>\n'
        material_select = f'<select name="material_id" required>{options_html}</select>'
    else:
        material_select = '<select name="material_id" disabled><option>请先到后台添加材质</option></select><p style="color:#c0392b;margin-top:-10px;margin-bottom:18px;font-size:13px;">暂无材质数据，请先到「添加材质」页面录入。</p>'

    # 构建客户下拉菜单（必选）
    if customers:
        cust_options = '<option value="">— 请选择客户 —</option>\n'
        for c in customers:
            selected = 'selected' if str(c['id']) == str(form_data['customer_id']) else ''
            phone_str = f' / {c["phone"]}' if c.get('phone') else ''
            cust_options += f'<option value="{c["id"]}" {selected}>{c["name"]}{phone_str}</option>\n'
        customer_select = f'<select name="customer_id" required>{cust_options}</select>'
    else:
        customer_select = '<select name="customer_id" required disabled><option value="">— 暂无客户，请先新建 —</option></select>'

    unit_sel = {
        'cm': 'selected' if form_data.get('unit', 'cm') == 'cm' else '',
        'mm': 'selected' if form_data.get('unit') == 'mm' else '',
        'm': 'selected' if form_data.get('unit') == 'm' else '',
    }

    content = f"""
    <div class="card">
      <h2>纸箱快速报价</h2>
      <div class="tip">先选择客户，再输入纸箱尺寸和数量，选择材质后系统自动计算用料面积与总价。优惠折扣按所选材质的规则自动匹配。支持毫米/厘米/米三种单位自动换算。</div>
      <form method="POST" action="/">
        <div class="form-row" style="margin-bottom:0;">
          <div class="form-group" style="flex:3;">
            <label>选择客户 <span style="color:#c0392b;">*</span></label>
            {customer_select}
          </div>
          <div class="form-group" style="flex:0 0 auto;align-self:flex-end;">
            <button type="button" class="btn-quick-add" onclick="toggleQuickCustomer()">＋ 快速新建</button>
          </div>
        </div>
        <div id="quick-cust-form" class="quick-cust-form" style="display:none;">
          <div class="form-row">
            <div class="form-group">
              <label>客户姓名 <span style="color:#c0392b;">*</span></label>
              <input type="text" id="quick-cust-name" placeholder="如：张老板">
            </div>
            <div class="form-group">
              <label>联系电话</label>
              <input type="text" id="quick-cust-phone" placeholder="如：13800138000">
            </div>
            <div class="form-group" style="flex:0 0 auto;align-self:flex-end;">
              <button type="button" class="btn" style="padding:10px 20px;font-size:14px;" onclick="submitQuickCustomer()">添加并选中</button>
            </div>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group" style="flex:0.5;">
            <label>尺寸单位</label>
            <select name="unit">
              <option value="cm" {unit_sel['cm']}>厘米</option>
              <option value="mm" {unit_sel['mm']}>毫米</option>
              <option value="m" {unit_sel['m']}>米</option>
            </select>
          </div>
          <div class="form-group">
            <label>长度</label>
            <input type="number" name="length" step="0.1" min="0" value="{form_data['length']}" placeholder="如：50.0" required>
          </div>
          <div class="form-group">
            <label>宽度</label>
            <input type="number" name="width" step="0.1" min="0" value="{form_data['width']}" placeholder="如：30.0" required>
          </div>
          <div class="form-group">
            <label>高度</label>
            <input type="number" name="height" step="0.1" min="0" value="{form_data['height']}" placeholder="如：20.0" required>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>数量 (个)</label>
            <input type="number" name="quantity" min="1" value="{form_data['quantity']}" placeholder="如：1000" required>
          </div>
          <div class="form-group" style="flex:2;">
            <label>选择材质规格</label>
            {material_select}
          </div>
        </div>
        <label>客户备注（可选）</label>
        <textarea name="remark" placeholder="记录客户需求，如：加急、定制印刷、送货地址等">{form_data['remark']}</textarea>
        <button type="submit" class="btn">立即计算报价</button>
      </form>
      {result_html}
    </div>
    """

    quick_add_js = """
  <style>
    .btn-quick-add {
      background: rgba(255,255,255,0.6);
      border: 1.5px dashed #8B5A2B;
      color: #8B5A2B;
      padding: 10px 16px;
      border-radius: 10px;
      cursor: pointer;
      font-size: 14px;
      white-space: nowrap;
      transition: all 0.2s;
    }
    .btn-quick-add:hover {
      background: rgba(139,90,43,0.1);
      border-style: solid;
    }
    .quick-cust-form {
      background: rgba(139,90,43,0.05);
      border: 1px dashed rgba(139,90,43,0.3);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 18px;
      margin-top: 8px;
    }
  </style>
  <script>
    function toggleQuickCustomer() {
      var f = document.getElementById('quick-cust-form');
      f.style.display = f.style.display === 'none' ? 'block' : 'none';
      if (f.style.display === 'block') {
        document.getElementById('quick-cust-name').focus();
      }
    }
    function submitQuickCustomer() {
      var name = document.getElementById('quick-cust-name').value.trim();
      var phone = document.getElementById('quick-cust-phone').value.trim();
      if (!name) { alert('请输入客户姓名'); return; }
      var fd = new FormData();
      fd.append('name', name);
      fd.append('phone', phone);
      fetch('/api/customers/quick-add', { method: 'POST', body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.success) {
            var sel = document.querySelector('select[name="customer_id"]');
            if (sel.disabled) { sel.disabled = false; sel.innerHTML = ''; }
            var opt = document.createElement('option');
            opt.value = data.customer.id;
            opt.textContent = data.customer.name + (data.customer.phone ? ' / ' + data.customer.phone : '');
            sel.appendChild(opt);
            sel.value = data.customer.id;
            document.getElementById('quick-cust-name').value = '';
            document.getElementById('quick-cust-phone').value = '';
            document.getElementById('quick-cust-form').style.display = 'none';
          } else {
            alert(data.message || '添加失败');
          }
        })
        .catch(function() { alert('网络错误，请重试'); });
    }
  </script>
    """

    return render_template_string(page_wrapper('首页报价器 - 新一骏纸品有限公司', 'home', content, quick_add_js))


# ============================================================
#  路由 2：添加材质（/add）— 含优惠档位录入
# ============================================================
@app.route('/add', methods=['GET', 'POST'])
def add():
    rules = load_rules()
    success_msg = ''
    form_data = {'name': '', 'length_addition': '', 'width_addition': '', 'unit_price': ''}

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        try:
            length_addition = float(request.form.get('length_addition', 0))
            width_addition = float(request.form.get('width_addition', 0))
            unit_price = float(request.form.get('unit_price', 0))
        except (ValueError, TypeError):
            length_addition = 0
            width_addition = 0
            unit_price = 0

        form_data = {
            'name': name,
            'length_addition': request.form.get('length_addition', ''),
            'width_addition': request.form.get('width_addition', ''),
            'unit_price': request.form.get('unit_price', '')
        }

        # 解析优惠档位
        min_qtys = request.form.getlist('discounts_min_qty[]')
        rates = request.form.getlist('discounts_rate[]')
        discounts = []
        for mq, r in zip(min_qtys, rates):
            try:
                mq_val = int(float(mq)) if mq.strip() else 0
                r_val = float(r) if r.strip() else 0
                if mq_val > 0 and 0 < r_val < 1:
                    discounts.append({'min_qty': mq_val, 'discount_rate': r_val})
            except (ValueError, TypeError):
                pass
        discounts.sort(key=lambda d: d['min_qty'])

        if name and length_addition >= 0 and width_addition >= 0 and unit_price >= 0:
            new_item = {
                'id': get_next_id(rules),
                'name': name,
                'length_addition': length_addition,
                'width_addition': width_addition,
                'unit_price': unit_price,
                'discounts': discounts,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            rules.append(new_item)
            save_rules(rules)

            total_count = len(rules)
            disc_count = len(discounts)
            disc_info = f'，含 {disc_count} 档优惠' if disc_count else ''
            success_msg = f'<div class="success-msg">添加成功！当前已录入 {total_count} 种材质规格{disc_info}。</div>'
            form_data = {'name': '', 'length_addition': '', 'width_addition': '', 'unit_price': ''}
        else:
            success_msg = '<div class="discount-notice">请填写完整的材质信息！</div>'

    current_count = len(rules)
    count_info = f'<div class="tip">当前系统已录入 <strong>{current_count}</strong> 种材质规格。</div>'

    content = f"""
    <div class="card">
      <h2>添加材质规格</h2>
      {count_info}
      {success_msg}
      <form method="POST" action="/add">
        <label>材质名称</label>
        <input type="text" name="name" value="{form_data['name']}" placeholder="如：A楞瓦楞纸 / 三层牛皮纸" required>

        <div class="form-row">
          <div class="form-group">
            <label>长度加放值 (cm)</label>
            <input type="number" name="length_addition" step="0.01" min="0" value="{form_data['length_addition']}" placeholder="如：2.5" required>
          </div>
          <div class="form-group">
            <label>宽度加放值 (cm)</label>
            <input type="number" name="width_addition" step="0.01" min="0" value="{form_data['width_addition']}" placeholder="如：2.5" required>
          </div>
        </div>

        <label>单价 (元/平方厘米)</label>
        <input type="number" name="unit_price" step="0.000001" min="0" value="{form_data['unit_price']}" placeholder="如：0.000035" required>

        <div class="discount-section">
          <label>优惠档位（可选）</label>
          <div class="discount-hint">为该材质设置阶梯优惠。折扣率 0.95 = 95折，数量达标自动生效。可添加多档，留空则该材质无优惠。</div>
          <div id="discount-container">
            <div class="discount-row">
              <input type="number" name="discounts_min_qty[]" min="1" placeholder="数量 >=" style="flex:1">
              <input type="number" name="discounts_rate[]" step="0.01" min="0.01" max="0.99" placeholder="折扣率 如 0.95" style="flex:1">
              <button type="button" class="btn-del-row" onclick="removeDiscountRow(this)">&#10005;</button>
            </div>
          </div>
          <button type="button" class="btn-add-row" onclick="addDiscountRow()">+ 添加优惠档位</button>
        </div>

        <button type="submit" class="btn">保存材质</button>
      </form>
    </div>
    """

    return render_template_string(page_wrapper('添加材质 - 新一骏纸品有限公司', 'add', content, DISCOUNT_JS))


# ============================================================
#  路由 3：材质数据（/list）
# ============================================================
@app.route('/list')
def view_list():
    rules = load_rules()

    if rules:
        rows_html = ''
        for r in rules:
            disc_text = format_discounts(r.get('discounts', []))
            disc_cell = f'<td class="disc-cell">{disc_text}</td>' if r.get('discounts') else '<td class="disc-cell"><span class="tag-none">—</span></td>'
            safe_name = r['name'].replace("'", "\\'")
            rows_html += f"""
            <tr>
              <td>{r['id']}</td>
              <td>{r['name']}</td>
              <td>{r['length_addition']:.2f}</td>
              <td>{r['width_addition']:.2f}</td>
              <td>{r['unit_price']:.6f}</td>
              {disc_cell}
              <td>{r.get('created_at', '未知')}</td>
              <td>
                <a href="/list/edit/{r['id']}" class="btn-link-edit">编辑</a>
                <a href="/list/delete/{r['id']}" class="btn-link-del" onclick="return confirm('确认删除材质「{safe_name}」？此操作不可撤销！')">删除</a>
              </td>
            </tr>
            """
        table_html = f"""
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>材质名称</th>
              <th>长加放 (cm)</th>
              <th>宽加放 (cm)</th>
              <th>单价 (元/c㎡)</th>
              <th>优惠规则</th>
              <th>录入时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
        <div class="table-footer">
          <span style="color:#7a8494;font-size:13px;">共 {len(rules)} 条材质数据</span>
          <a href="/list/clear-all" class="btn-clear-all" onclick="return confirm('⚠️ 确认清空全部材质数据？此操作不可撤销！')">清空全部材质</a>
        </div>
        """
    else:
        table_html = '<div class="empty-msg">暂无材质数据，请先到「添加材质」页面录入。</div>'

    content = f"""
    <div class="card">
      <h2>全部材质数据</h2>
      {table_html}
    </div>
    """

    return render_template_string(page_wrapper('材质数据 - 新一骏纸品有限公司', 'list', content))


# ============================================================
#  路由 4：报价记录（/quotes）
# ============================================================
@app.route('/quotes')
def view_quotes():
    quotes = load_quotes()
    customers = load_customers()

    # === 搜索筛选 ===
    keyword = request.args.get('keyword', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    customer_filter = request.args.get('customer', '').strip()

    filtered = quotes
    if keyword:
        kw = keyword.lower()
        filtered = [q for q in filtered if kw in q.get('quote_no', '').lower()
                    or kw in q.get('material_name', '').lower()
                    or kw in q.get('remark', '').lower()
                    or kw in q.get('customer_name', '').lower()]
    if date_from:
        filtered = [q for q in filtered if q.get('created_at', '') >= date_from]
    if date_to:
        filtered = [q for q in filtered if q.get('created_at', '')[:10] <= date_to]
    if customer_filter:
        filtered = [q for q in filtered if str(q.get('customer_id', '')) == customer_filter]

    if filtered:
        rows_html = ''
        for q in reversed(filtered):  # 最新的排前面
            disc_col = q['discount_desc'] if q.get('discount_rate') else '<span class="tag-none">—</span>'
            remark = q.get('remark', '') or ''
            remark_cell = f'<td class="remark-cell">{remark}</td>' if remark else '<td class="remark-cell"><span class="tag-none">—</span></td>'
            q_unit = q.get('input_unit', 'cm')
            q_no = q.get('quote_no', f'QJ{q["id"]:08d}')
            cust_name = q.get('customer_name', '') or '<span class="tag-none">—</span>'
            rows_html += f"""
            <tr>
              <td style="color:#8B5A2B;font-weight:600;font-size:13px;">{q_no}</td>
              <td>{cust_name}</td>
              <td>{q['material_name']}</td>
              <td>{q['length']:.1f}×{q['width']:.1f}×{q['height']:.1f} {q_unit}</td>
              <td>{q['quantity']}</td>
              <td>{q['original_total']:.2f}</td>
              <td>{disc_col}</td>
              <td><strong style="color:#c0a062;">{q['final_total']:.2f}</strong></td>
              {remark_cell}
              <td>{q.get('created_at', '未知')}</td>
              <td><a href="/quotes/delete/{q['id']}" class="btn-link-del" onclick="return confirm('确认删除报价单「{q_no}」？')">删除</a></td>
            </tr>
            """
        result_summary = f'共 {len(filtered)} 条'
        if len(filtered) < len(quotes):
            result_summary += f'（筛选自 {len(quotes)} 条）'
        table_html = f"""
        <table>
          <thead>
            <tr>
              <th>报价单号</th>
              <th>客户</th>
              <th>材质</th>
              <th>尺寸</th>
              <th>数量</th>
              <th>原价(元)</th>
              <th>折扣</th>
              <th>实付(元)</th>
              <th>客户备注</th>
              <th>报价时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
        <div class="table-footer">
          <span style="color:#7a8494;font-size:13px;">{result_summary}</span>
          <a href="/quotes/clear-all" class="btn-clear-all" onclick="return confirm('⚠️ 确认清空全部报价记录？此操作不可撤销！')">清空全部记录</a>
        </div>
        """
    else:
        has_filter = keyword or date_from or date_to or customer_filter
        empty_msg = '没有找到匹配的报价记录，试试调整搜索条件。' if has_filter else '暂无报价记录，去首页报价器生成第一条吧。'
        table_html = f'<div class="empty-msg">{empty_msg}</div>'

    # 客户筛选下拉
    cust_filter_options = '<option value="">全部客户</option>\n'
    for c in customers:
        selected = 'selected' if str(c['id']) == customer_filter else ''
        cust_filter_options += f'<option value="{c["id"]}" {selected}>{c["name"]}</option>\n'

    # 搜索栏
    search_html = f"""
    <div class="search-bar">
      <form method="GET" action="/quotes" class="search-form">
        <input type="text" name="keyword" value="{keyword}" placeholder="搜报价单号 / 客户 / 材质 / 备注…" class="search-input">
        <select name="customer" class="search-date" style="min-width:120px;">
          {cust_filter_options}
        </select>
        <input type="date" name="date_from" value="{date_from}" class="search-date" title="开始日期">
        <span style="color:#999;">~</span>
        <input type="date" name="date_to" value="{date_to}" class="search-date" title="结束日期">
        <button type="submit" class="search-btn">搜索</button>
        {'<a href="/quotes" class="search-reset">清除筛选</a>' if (keyword or date_from or date_to or customer_filter) else ''}
      </form>
    </div>
    """

    content = f"""
    <div class="card">
      <h2>报价记录</h2>
      <div class="tip">每次在首页报价器提交报价后，记录会自动保存在此。可按报价单号、材质、备注或日期筛选。</div>
      {search_html}
      {table_html}
    </div>
    """

    return render_template_string(page_wrapper('报价记录 - 新一骏纸品有限公司', 'quotes', content))


@app.route('/quotes/delete/<int:qid>')
def delete_quote(qid):
    quotes = load_quotes()
    quotes = [q for q in quotes if q['id'] != qid]
    save_quotes(quotes)
    return redirect('/quotes')


@app.route('/quotes/clear-all')
def clear_all_quotes():
    save_quotes([])
    return redirect('/quotes')


# ============================================================
#  路由 5：客户管理（/customers）
# ============================================================
@app.route('/customers', methods=['GET', 'POST'])
def view_customers():
    customers = load_customers()

    if request.method == 'POST':
        # 添加客户
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        company = request.form.get('company', '').strip()
        address = request.form.get('address', '').strip()

        if name:
            customer = {
                'id': get_next_id(customers),
                'name': name,
                'phone': phone,
                'company': company,
                'address': address,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            customers.append(customer)
            save_customers(customers)

        return redirect('/customers')

    # 搜索
    keyword = request.args.get('keyword', '').strip()
    filtered = customers
    if keyword:
        kw = keyword.lower()
        filtered = [c for c in filtered if kw in c.get('name', '').lower()
                    or kw in c.get('phone', '').lower()
                    or kw in c.get('company', '').lower()
                    or kw in c.get('address', '').lower()]

    if filtered:
        rows_html = ''
        for c in reversed(filtered):
            phone_cell = c.get('phone', '') or '<span class="tag-none">—</span>'
            company_cell = c.get('company', '') or '<span class="tag-none">—</span>'
            addr_cell = c.get('address', '') or '<span class="tag-none">—</span>'
            safe_name = c['name'].replace("'", "\\'")
            rows_html += f"""
            <tr>
              <td>{c['id']}</td>
              <td><strong>{c['name']}</strong></td>
              <td>{phone_cell}</td>
              <td>{company_cell}</td>
              <td>{addr_cell}</td>
              <td>{c.get('created_at', '未知')}</td>
              <td>
                <a href="/customers/edit/{c['id']}" class="btn-link-edit">编辑</a>
                <a href="/customers/delete/{c['id']}" class="btn-link-del" onclick="return confirm('确认删除客户「{safe_name}」？此操作不可撤销！')">删除</a>
              </td>
            </tr>
            """
        result_summary = f'共 {len(filtered)} 条'
        if len(filtered) < len(customers):
            result_summary += f'（筛选自 {len(customers)} 条）'
        table_html = f"""
        <table>
          <thead>
            <tr>
              <th>编号</th>
              <th>客户姓名</th>
              <th>电话</th>
              <th>公司名</th>
              <th>地址</th>
              <th>录入时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
        <div class="table-footer">
          <span style="color:#7a8494;font-size:13px;">{result_summary}</span>
          <a href="/customers/clear-all" class="btn-clear-all" onclick="return confirm('⚠️ 确认清空全部客户数据？此操作不可撤销！')">清空全部客户</a>
        </div>
        """
    else:
        empty_msg = '没有找到匹配的客户，试试调整搜索。' if keyword else '暂无客户数据，在上方添加第一个客户吧。'
        table_html = f'<div class="empty-msg">{empty_msg}</div>'

    search_html = f"""
    <div class="search-bar">
      <form method="GET" action="/customers" class="search-form">
        <input type="text" name="keyword" value="{keyword}" placeholder="搜客户名 / 电话 / 公司 / 地址…" class="search-input">
        <button type="submit" class="search-btn">搜索</button>
        {'<a href="/customers" class="search-reset">清除筛选</a>' if keyword else ''}
      </form>
    </div>
    """

    # 添加客户表单
    add_form = """
    <div class="card" style="margin-bottom: 20px;">
      <h2>添加客户</h2>
      <div class="tip">录入客户信息，报价时可直接选择关联。</div>
      <form method="POST" action="/customers">
        <div class="form-row">
          <div class="form-group">
            <label>客户姓名 *</label>
            <input type="text" name="name" required placeholder="如：张先生">
          </div>
          <div class="form-group">
            <label>联系电话</label>
            <input type="text" name="phone" placeholder="如：13800138000">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>公司名称</label>
            <input type="text" name="company" placeholder="如：XX包装有限公司">
          </div>
          <div class="form-group" style="flex:2;">
            <label>送货地址</label>
            <input type="text" name="address" placeholder="如：XX市XX区XX路XX号">
          </div>
        </div>
        <button type="submit" class="btn">添加客户</button>
      </form>
    </div>
    """

    content = f"""
    {add_form}
    <div class="card">
      <h2>客户列表</h2>
      <div class="tip">管理所有客户信息，支持按姓名、电话、公司、地址搜索。</div>
      {search_html}
      {table_html}
    </div>
    """

    return render_template_string(page_wrapper('客户管理 - 新一骏纸品有限公司', 'customers', content))


@app.route('/customers/edit/<int:cid>', methods=['GET', 'POST'])
def edit_customer(cid):
    customers = load_customers()
    customer = None
    for c in customers:
        if c['id'] == cid:
            customer = c
            break

    if not customer:
        return redirect('/customers')

    if request.method == 'POST':
        customer['name'] = request.form.get('name', '').strip()
        customer['phone'] = request.form.get('phone', '').strip()
        customer['company'] = request.form.get('company', '').strip()
        customer['address'] = request.form.get('address', '').strip()
        customer['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_customers(customers)

        success_msg = '<div class="discount-notice" style="background:rgba(139,90,43,0.08);color:#8B5A2B;border-color:rgba(139,90,43,0.2);">✓ 客户信息修改成功！</div>'
    else:
        success_msg = ''

    content = f"""
    <div class="card">
      <h2>编辑客户</h2>
      {success_msg}
      <form method="POST" action="/customers/edit/{cid}">
        <div class="form-row">
          <div class="form-group">
            <label>客户姓名 *</label>
            <input type="text" name="name" value="{customer['name']}" required>
          </div>
          <div class="form-group">
            <label>联系电话</label>
            <input type="text" name="phone" value="{customer.get('phone', '')}">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>公司名称</label>
            <input type="text" name="company" value="{customer.get('company', '')}">
          </div>
          <div class="form-group" style="flex:2;">
            <label>送货地址</label>
            <input type="text" name="address" value="{customer.get('address', '')}">
          </div>
        </div>
        <button type="submit" class="btn">保存修改</button>
        <a href="/customers" class="btn-link-edit" style="margin-left:10px;">← 返回列表</a>
      </form>
    </div>
    """

    return render_template_string(page_wrapper('编辑客户 - 新一骏纸品有限公司', 'customers', content))


@app.route('/customers/delete/<int:cid>')
def delete_customer(cid):
    customers = load_customers()
    customers = [c for c in customers if c['id'] != cid]
    save_customers(customers)
    return redirect('/customers')


@app.route('/customers/clear-all')
def clear_all_customers():
    save_customers([])
    return redirect('/customers')


# ============================================================
#  API：报价器内快速新建客户（AJAX）
# ============================================================
@app.route('/api/customers/quick-add', methods=['POST'])
def quick_add_customer():
    customers = load_customers()
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '客户姓名不能为空'})
    customer = {
        'id': get_next_id(customers),
        'name': name,
        'phone': phone,
        'company': '',
        'address': '',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    customers.append(customer)
    save_customers(customers)
    return jsonify({'success': True, 'customer': customer})


# ============================================================
#  路由：删除材质 / 清空材质
# ============================================================
@app.route('/list/delete/<int:rid>')
def delete_material(rid):
    rules = load_rules()
    rules = [r for r in rules if r['id'] != rid]
    save_rules(rules)
    return redirect('/list')


@app.route('/list/clear-all')
def clear_all_materials():
    save_rules([])
    return redirect('/list')


# ============================================================
#  路由：编辑材质
# ============================================================
@app.route('/list/edit/<int:rid>', methods=['GET', 'POST'])
def edit_material(rid):
    rules = load_rules()
    material = None
    for r in rules:
        if r['id'] == rid:
            material = r
            break

    if not material:
        return redirect('/list')

    success_msg = ''

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        try:
            length_addition = float(request.form.get('length_addition', 0))
            width_addition = float(request.form.get('width_addition', 0))
            unit_price = float(request.form.get('unit_price', 0))
        except (ValueError, TypeError):
            length_addition = 0
            width_addition = 0
            unit_price = 0

        # 解析优惠档位
        min_qtys = request.form.getlist('discounts_min_qty[]')
        rates = request.form.getlist('discounts_rate[]')
        discounts = []
        for mq, rt in zip(min_qtys, rates):
            try:
                mq_val = int(float(mq)) if mq.strip() else 0
                r_val = float(rt) if rt.strip() else 0
                if mq_val > 0 and 0 < r_val < 1:
                    discounts.append({'min_qty': mq_val, 'discount_rate': r_val})
            except (ValueError, TypeError):
                pass
        discounts.sort(key=lambda d: d['min_qty'])

        if name and length_addition >= 0 and width_addition >= 0 and unit_price >= 0:
            material['name'] = name
            material['length_addition'] = length_addition
            material['width_addition'] = width_addition
            material['unit_price'] = unit_price
            material['discounts'] = discounts
            material['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            save_rules(rules)
            success_msg = f'<div class="success-msg">材质「{name}」修改成功！</div>'
            for r in rules:
                if r['id'] == rid:
                    material = r
                    break
        else:
            success_msg = '<div class="discount-notice">请填写完整的材质信息！</div>'

    # 构建优惠档位行（预填已有数据）
    existing_discounts = material.get('discounts', [])
    if existing_discounts:
        disc_rows = ''
        for d in existing_discounts:
            disc_rows += f"""
            <div class="discount-row">
              <input type="number" name="discounts_min_qty[]" min="1" value="{d['min_qty']}" placeholder="数量 >=" style="flex:1">
              <input type="number" name="discounts_rate[]" step="0.01" min="0.01" max="0.99" value="{d['discount_rate']}" placeholder="折扣率 如 0.95" style="flex:1">
              <button type="button" class="btn-del-row" onclick="removeDiscountRow(this)">&#10005;</button>
            </div>"""
    else:
        disc_rows = """
            <div class="discount-row">
              <input type="number" name="discounts_min_qty[]" min="1" placeholder="数量 >=" style="flex:1">
              <input type="number" name="discounts_rate[]" step="0.01" min="0.01" max="0.99" placeholder="折扣率 如 0.95" style="flex:1">
              <button type="button" class="btn-del-row" onclick="removeDiscountRow(this)">&#10005;</button>
            </div>"""

    content = f"""
    <div class="card">
      <h2>编辑材质 — {material['name']}</h2>
      {success_msg}
      <form method="POST" action="/list/edit/{rid}">
        <label>材质名称</label>
        <input type="text" name="name" value="{material['name']}" placeholder="如：A楞瓦楞纸 / 三层牛皮纸" required>

        <div class="form-row">
          <div class="form-group">
            <label>长度加放值 (cm)</label>
            <input type="number" name="length_addition" step="0.01" min="0" value="{material['length_addition']}" placeholder="如：2.5" required>
          </div>
          <div class="form-group">
            <label>宽度加放值 (cm)</label>
            <input type="number" name="width_addition" step="0.01" min="0" value="{material['width_addition']}" placeholder="如：2.5" required>
          </div>
        </div>

        <label>单价 (元/平方厘米)</label>
        <input type="number" name="unit_price" step="0.000001" min="0" value="{material['unit_price']}" placeholder="如：0.000035" required>

        <div class="discount-section">
          <label>优惠档位（可选）</label>
          <div class="discount-hint">为该材质设置阶梯优惠。折扣率 0.95 = 95折，数量达标自动生效。可添加多档，留空则该材质无优惠。</div>
          <div id="discount-container">
            {disc_rows}
          </div>
          <button type="button" class="btn-add-row" onclick="addDiscountRow()">+ 添加优惠档位</button>
        </div>

        <button type="submit" class="btn">保存修改</button>
        <a href="/list" style="display:inline-block;margin-left:12px;color:#8B7355;font-size:14px;text-decoration:none;">&larr; 返回列表</a>
      </form>
    </div>
    """

    return render_template_string(page_wrapper('编辑材质 - 新一骏纸品有限公司', 'list', content, DISCOUNT_JS))


# ============================================================
#  启动
# ============================================================
if __name__ == '__main__':
    # 启动时确保数据文件存在
    load_rules()
    load_customers()
    _quotes = load_quotes()
    # 为历史报价记录补充编号
    if backfill_quote_no(_quotes):
        save_quotes(_quotes)
        print(f"  已为 {_quotes.__len__()} 条历史报价记录补充编号")
    # 本地开发模式（debug=True）；生产环境通过 wsgi.py + Gunicorn 启动
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    print("=" * 50)
    print("  新一骏纸品有限公司 - 智能报价系统")
    print(f"  访问地址: http://127.0.0.1:5000  (debug={debug_mode})")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
