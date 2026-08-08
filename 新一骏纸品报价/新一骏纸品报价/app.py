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
#  公司信息（打印报价单用，可自行修改）
# ============================================================
COMPANY_NAME = '新一骏纸品有限公司'
COMPANY_PHONE = '138-0000-0000'          # ← 改成你的电话
COMPANY_ADDRESS = '请修改为实际地址'       # ← 改成你的地址

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

  /* ===== 打印按钮 ===== */
  .btn-print {
    display: block;
    width: 100%;
    margin-top: 20px;
    padding: 12px;
    background: #8B5A2B;
    color: #fff !important;
    border: none;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 600;
    text-align: center;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-print:hover {
    background: #6B4423;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(139,90,43,0.3);
  }

  /* ===== 报价单文档（首页内嵌） ===== */
  .quote-doc {
    background: #fff;
    border-radius: 14px;
    padding: 36px 40px;
    margin-top: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    max-width: 780px;
    margin-left: auto;
    margin-right: auto;
  }
  .quote-doc .doc-header { text-align:center; border-bottom:3px double #8B5A2B; padding-bottom:18px; margin-bottom:22px; }
  .quote-doc .doc-header h1 { font-size:24px; color:#8B5A2B; margin-bottom:6px; letter-spacing:2px; }
  .quote-doc .doc-header .contact { font-size:13px; color:#999; }
  .quote-doc .doc-bar { display:flex; justify-content:space-between; align-items:center; margin-bottom:22px; }
  .quote-doc .doc-bar .qno { font-size:18px; color:#8B5A2B; font-weight:700; }
  .quote-doc .doc-bar .date { font-size:13px; color:#888; }
  .quote-doc .doc-title { font-size:15px; color:#8B5A2B; font-weight:bold; border-left:4px solid #8B5A2B; padding-left:8px; margin:18px 0 10px; }
  .quote-doc .two-col { display:flex; gap:16px; }
  .quote-doc .two-col > div { flex:1; }
  .quote-doc table.info { width:100%; border-collapse:collapse; margin-bottom:8px; }
  .quote-doc table.info td { padding:7px 12px; border:1px solid #e8e0d5; font-size:14px; }
  .quote-doc table.info td.label { width:100px; color:#8B7355; background:#faf8f5; font-weight:500; }
  .quote-doc table.detail { width:100%; border-collapse:collapse; margin-bottom:8px; }
  .quote-doc table.detail th { background:#8B5A2B; color:#fff; padding:8px; font-size:13px; font-weight:500; text-align:left; }
  .quote-doc table.detail td { padding:8px 12px; border:1px solid #e0d5c8; font-size:14px; }
  .quote-doc .total-bar { display:flex; justify-content:flex-end; margin:14px 0; }
  .quote-doc .total-box { background:#fdf5e6; border:2px solid #8B5A2B; border-radius:8px; padding:10px 28px; text-align:center; }
  .quote-doc .total-box .lbl { font-size:13px; color:#8B7355; }
  .quote-doc .total-box .val { font-size:24px; color:#8B5A2B; font-weight:700; }
  .quote-doc .total-box .val .y { font-size:14px; }
  .quote-doc .remark-area { background:#faf8f5; border:1px solid #e0d5c8; border-radius:6px; padding:12px 16px; margin:14px 0; font-size:14px; color:#5a5045; }
  .quote-doc .remark-area .rm-lbl { color:#8B5A2B; font-weight:bold; margin-right:8px; }
  .quote-doc .sign-area { display:flex; justify-content:space-between; margin-top:40px; padding-top:20px; }
  .quote-doc .sign-box { text-align:center; }
  .quote-doc .sign-box .sign-line { width:200px; border-bottom:1px solid #999; margin-bottom:6px; }
  .quote-doc .sign-box .sign-lbl { font-size:13px; color:#888; }
  .quote-doc .doc-footer { text-align:center; margin-top:30px; padding-top:14px; border-top:1px solid #eee; font-size:12px; color:#bbb; }
  .quote-doc .doc-actions { text-align:center; margin-top:20px; }

  /* ===== 打印：只显示报价单 ===== */
  @media print {
    .header, .nav, .footer, .container > .card > .tip,
    .container > .card > form, .container > .card > .quote-form,
    .btn-print, .no-print { display: none !important; }
    body { background: #fff !important; }
    .container { max-width: none !important; padding: 0 !important; margin: 0 !important; }
    .card { background: none !important; box-shadow: none !important; border: none !important; backdrop-filter: none !important; padding: 0 !important; }
    .quote-doc { box-shadow: none !important; padding: 20px !important; max-width: none !important; }
    .quote-doc .doc-actions { display: none !important; }
    .quote-doc select, .quote-doc input {
      border: none !important; background: none !important;
      -webkit-appearance: none !important; appearance: none !important;
      width: auto !important; padding: 0 !important; margin: 0 !important;
    }
    .quote-doc .dim-x, .quote-doc .btn-quick-inline, .quick-cust-inline { display: none !important; }
    .quote-doc .remark-input { border: none !important; }
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
  .btn-link {
    color: #8B5A2B;
    text-decoration: none;
    font-size: 12px;
    padding: 4px 10px;
    border: 1px solid rgba(139,90,43,0.25);
    border-radius: 5px;
    transition: background 0.2s, color 0.2s, border-color 0.2s;
    margin-right: 4px;
  }
  .btn-link:hover {
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


# -*- coding: utf-8 -*-
"""New index function + API endpoint for app.py"""

# ============================================================
#  路由 1：首页报价器（/）— 表单即报价单，一体化出单
# ============================================================
@app.route('/')
def index():
    rules = load_rules()
    customers = load_customers()

    today = datetime.now().strftime('%Y-%m-%d')
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 构建客户下拉菜单
    if customers:
        cust_options = '<option value="">— 请选择客户 —</option>\n'
        for c in customers:
            phone_str = f' / {c["phone"]}' if c.get('phone') else ''
            cust_options += f'<option value="{c["id"]}">{c["name"]}{phone_str}</option>\n'
        customer_select = f'<select id="customer_id" onchange="onCustomerChange()">{cust_options}</select>'
    else:
        customer_select = '<select id="customer_id" disabled><option value="">— 暂无客户 —</option></select>'

    # 构建材质下拉菜单
    if rules:
        mat_options = '<option value="">— 请选择材质 —</option>\n'
        for r in rules:
            mat_options += f'<option value="{r["id"]}">{r["name"]}</option>\n'
        material_select = f'<select id="material_id" onchange="calcPrice()">{mat_options}</select>'
    else:
        material_select = '<select id="material_id" disabled><option value="">请先添加材质</option></select>'

    # JSON 数据传给 JS
    materials_json = json.dumps(rules, ensure_ascii=False)
    customers_json = json.dumps(customers, ensure_ascii=False)

    content = f"""
    <div class="quote-doc" id="quote-doc">
      <div class="doc-header">
        <h1>{COMPANY_NAME}</h1>
        <div class="contact">地址：{COMPANY_ADDRESS}　｜　电话：{COMPANY_PHONE}</div>
      </div>
      <div class="doc-bar">
        <div class="qno" id="doc-qno">待生成</div>
        <div class="date">制单日期：{today}</div>
      </div>
      <div class="two-col">
        <div>
          <div class="doc-title">客户信息</div>
          <table class="info">
            <tr><td class="label">客户名称</td><td class="td-input">{customer_select}<button type="button" class="btn-quick-inline" onclick="toggleQuickCustomer()">＋</button></td></tr>
            <tr><td class="label">联系电话</td><td id="cust-phone">—</td></tr>
            <tr><td class="label">公司名称</td><td id="cust-company">—</td></tr>
            <tr><td class="label">送货地址</td><td id="cust-address">—</td></tr>
          </table>
          <div id="quick-cust-form" class="quick-cust-inline" style="display:none;">
            <input type="text" id="quick-cust-name" placeholder="姓名" class="mini-input">
            <input type="text" id="quick-cust-phone" placeholder="电话" class="mini-input">
            <button type="button" class="btn-mini" onclick="submitQuickCustomer()">添加</button>
          </div>
        </div>
        <div>
          <div class="doc-title">报价概况</div>
          <table class="info">
            <tr><td class="label">选用材质</td><td class="td-input">{material_select}</td></tr>
            <tr><td class="label">尺寸(长×宽×高)</td><td class="td-input">
              <input type="number" id="dim-l" step="0.1" min="0" placeholder="长" class="dim-input" oninput="calcPrice()">
              <span class="dim-x">×</span>
              <input type="number" id="dim-w" step="0.1" min="0" placeholder="宽" class="dim-input" oninput="calcPrice()">
              <span class="dim-x">×</span>
              <input type="number" id="dim-h" step="0.1" min="0" placeholder="高" class="dim-input" oninput="calcPrice()">
              <select id="dim-unit" onchange="calcPrice()" class="unit-sel">
                <option value="cm">cm</option>
                <option value="mm">mm</option>
                <option value="m">m</option>
              </select>
            </td></tr>
            <tr><td class="label">数量</td><td class="td-input"><input type="number" id="dim-qty" min="1" placeholder="如：1000" class="qty-input" oninput="calcPrice()"> 个</td></tr>
            <tr><td class="label">报价时间</td><td>{now_str}</td></tr>
          </table>
        </div>
      </div>
      <div class="doc-title">价格明细</div>
      <table class="detail">
        <tr><th>项目</th><th>数值</th></tr>
        <tr><td>长度加放</td><td id="d-len-add">—</td></tr>
        <tr><td>宽度加放</td><td id="d-wid-add">—</td></tr>
        <tr><td>用料面积</td><td id="d-area">—</td></tr>
        <tr><td>纸质单价</td><td id="d-price">—</td></tr>
        <tr><td>原始总价</td><td id="d-original">—</td></tr>
        <tr><td>优惠信息</td><td id="d-discount">—</td></tr>
      </table>
      <div class="total-bar">
        <div class="total-box">
          <div class="lbl">最终应付总价</div>
          <div class="val" id="d-final">0.00<span class="y"> 元</span></div>
        </div>
      </div>
      <div class="remark-area">
        <span class="rm-lbl">备注</span>
        <input type="text" id="doc-remark" placeholder="记录客户需求，如：加急、定制印刷、送货等" class="remark-input">
      </div>
      <div class="sign-area">
        <div class="sign-box">
          <div class="sign-line"></div>
          <div class="sign-lbl">供方签字（盖章）</div>
        </div>
        <div class="sign-box">
          <div class="sign-line"></div>
          <div class="sign-lbl">客户签字确认</div>
        </div>
      </div>
      <div class="doc-footer">本报价单自制单日起30天内有效 · {COMPANY_NAME}</div>
      <div class="doc-actions no-print">
        <button type="button" onclick="saveAndPrint()" class="btn-print" style="display:inline-block;width:auto;padding:12px 40px;">保存并打印</button>
        <span id="save-status" style="margin-left:12px;color:#8B5A2B;font-size:14px;"></span>
      </div>
    </div>
    <script>
    var MATERIALS = {materials_json};
    var CUSTOMERS = {customers_json};
    </script>
    """

    page_js = """
  <style>
    .quote-doc .td-input { display:flex; align-items:center; gap:4px; flex-wrap:wrap; }
    .quote-doc select {
      border: 1px solid #e0d5c8; border-radius: 4px; padding: 4px 8px;
      font-size: 14px; background: #fff; color: #333; cursor: pointer; max-width: 180px;
    }
    .quote-doc .dim-input {
      width: 52px; border: 1px solid #e0d5c8; border-radius: 4px; padding: 4px 6px;
      font-size: 14px; text-align: center; background: #fff;
    }
    .quote-doc .dim-x { color: #aaa; font-size: 13px; }
    .quote-doc .unit-sel {
      width: 56px; border: 1px solid #e0d5c8; border-radius: 4px; padding: 4px 4px;
      font-size: 13px; background: #fff; margin-left: 4px;
    }
    .quote-doc .qty-input {
      width: 90px; border: 1px solid #e0d5c8; border-radius: 4px; padding: 4px 8px; font-size: 14px;
    }
    .quote-doc .remark-input {
      border: none; background: transparent; width: 80%; outline: none;
      font-size: 14px; color: #5a5045; font-family: inherit;
    }
    .quote-doc .remark-input:focus { border-bottom: 1px dashed #8B5A2B; }
    .btn-quick-inline {
      background: rgba(139,90,43,0.1); border: 1px dashed #8B5A2B; color: #8B5A2B;
      width: 24px; height: 24px; border-radius: 50%; cursor: pointer; font-size: 14px;
      line-height: 1; padding: 0; display: inline-flex; align-items: center; justify-content: center;
    }
    .btn-quick-inline:hover { background: #8B5A2B; color: #fff; }
    .quick-cust-inline {
      display: flex; gap: 6px; align-items: center; margin-top: 8px; padding: 8px;
      background: rgba(139,90,43,0.05); border-radius: 6px;
    }
    .mini-input {
      border: 1px solid #e0d5c8; border-radius: 4px; padding: 4px 8px; font-size: 13px; width: 80px;
    }
    .btn-mini {
      background: #8B5A2B; color: #fff; border: none; border-radius: 4px;
      padding: 5px 12px; font-size: 13px; cursor: pointer;
    }
    .btn-mini:hover { background: #6B4423; }
    .calc-error {
      text-align: center; color: #c0392b; font-size: 14px; padding: 12px;
      background: rgba(192,57,43,0.05); border-radius: 8px; margin-top: 12px;
    }
  </style>
  <script>
    function onCustomerChange() {
      var sel = document.getElementById('customer_id');
      var id = parseInt(sel.value) || 0;
      var c = CUSTOMERS.find(function(x) { return x.id === id; });
      if (c) {
        document.getElementById('cust-phone').textContent = c.phone || '—';
        document.getElementById('cust-company').textContent = c.company || '—';
        document.getElementById('cust-address').textContent = c.address || '—';
      } else {
        document.getElementById('cust-phone').textContent = '—';
        document.getElementById('cust-company').textContent = '—';
        document.getElementById('cust-address').textContent = '—';
      }
      calcPrice();
    }

    function calcPrice() {
      var matId = parseInt(document.getElementById('material_id').value) || 0;
      var qty = parseInt(document.getElementById('dim-qty').value) || 0;
      var l = parseFloat(document.getElementById('dim-l').value) || 0;
      var w = parseFloat(document.getElementById('dim-w').value) || 0;
      var h = parseFloat(document.getElementById('dim-h').value) || 0;
      var unit = document.getElementById('dim-unit').value;

      var mat = MATERIALS.find(function(x) { return x.id === matId; });
      if (!mat || l <= 0 || w <= 0 || qty <= 0) {
        document.getElementById('d-len-add').textContent = mat ? mat.length_addition.toFixed(2) + ' cm' : '—';
        document.getElementById('d-wid-add').textContent = mat ? mat.width_addition.toFixed(2) + ' cm' : '—';
        document.getElementById('d-area').textContent = '—';
        document.getElementById('d-price').textContent = mat ? mat.unit_price.toFixed(6) + ' 元/c㎡' : '—';
        document.getElementById('d-original').textContent = '—';
        document.getElementById('d-discount').textContent = '—';
        document.getElementById('d-final').innerHTML = '0.00<span class="y"> 元</span>';
        return;
      }

      var factor = {mm: 0.1, cm: 1.0, m: 100.0}[unit] || 1.0;
      var lcm = l * factor, wcm = w * factor;
      var lenAdd = mat.length_addition, widAdd = mat.width_addition;
      var area = (lcm + lenAdd) * (wcm + widAdd) * 2 * qty;
      var original = area * mat.unit_price;

      var discounts = mat.discounts || [];
      var applicable = discounts.filter(function(d) { return d.min_qty <= qty; });
      var hasDiscount = applicable.length > 0;
      var rate = 1.0;
      var discText = '无优惠';
      if (hasDiscount) {
        var best = applicable.reduce(function(a, b) { return a.min_qty >= b.min_qty ? a : b; });
        rate = best.discount_rate;
        var saved = original - original * rate;
        var pct = rate * 100;
        var discStr = (pct % 10 === 0) ? (parseInt(pct / 10) + '折') : (parseInt(pct) + '折');
        discText = discStr + '（省 ' + saved.toFixed(2) + ' 元）';
      }
      var final = original * rate;

      document.getElementById('d-len-add').textContent = lenAdd.toFixed(2) + ' cm';
      document.getElementById('d-wid-add').textContent = widAdd.toFixed(2) + ' cm';
      document.getElementById('d-area').textContent = area.toFixed(2) + ' 平方厘米';
      document.getElementById('d-price').textContent = mat.unit_price.toFixed(6) + ' 元/c㎡';
      document.getElementById('d-original').textContent = original.toFixed(2) + ' 元';
      document.getElementById('d-discount').textContent = discText;
      document.getElementById('d-final').innerHTML = final.toFixed(2) + '<span class="y"> 元</span>';
    }

    function saveAndPrint() {
      var custId = document.getElementById('customer_id').value;
      var matId = document.getElementById('material_id').value;
      var l = document.getElementById('dim-l').value;
      var w = document.getElementById('dim-w').value;
      var h = document.getElementById('dim-h').value;
      var qty = document.getElementById('dim-qty').value;
      var unit = document.getElementById('dim-unit').value;
      var remark = document.getElementById('doc-remark').value.trim();

      var status = document.getElementById('save-status');
      status.textContent = '正在保存...';

      if (!custId) { status.textContent = ''; alert('请先选择客户'); return; }
      if (!matId) { status.textContent = ''; alert('请先选择材质'); return; }
      if (!l || !w || parseFloat(l) <= 0 || parseFloat(w) <= 0) { status.textContent = ''; alert('请输入有效的尺寸'); return; }
      if (!qty || parseInt(qty) <= 0) { status.textContent = ''; alert('请输入有效的数量'); return; }

      var fd = new FormData();
      fd.append('customer_id', custId);
      fd.append('material_id', matId);
      fd.append('length', l);
      fd.append('width', w);
      fd.append('height', h || 0);
      fd.append('quantity', qty);
      fd.append('unit', unit);
      fd.append('remark', remark);

      fetch('/api/quote/save', { method: 'POST', body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.success) {
            document.getElementById('doc-qno').textContent = data.quote_no;
            status.textContent = '已保存，正在打印...';
            setTimeout(function() { window.print(); }, 300);
          } else {
            status.textContent = '';
            alert(data.message || '保存失败');
          }
        })
        .catch(function() { status.textContent = ''; alert('网络错误，请重试'); });
    }

    function toggleQuickCustomer() {
      var f = document.getElementById('quick-cust-form');
      f.style.display = f.style.display === 'none' ? 'flex' : 'none';
      if (f.style.display === 'flex') document.getElementById('quick-cust-name').focus();
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
            CUSTOMERS.push(data.customer);
            var sel = document.getElementById('customer_id');
            if (sel.disabled) { sel.disabled = false; sel.innerHTML = ''; }
            var opt = document.createElement('option');
            opt.value = data.customer.id;
            opt.textContent = data.customer.name + (data.customer.phone ? ' / ' + data.customer.phone : '');
            sel.appendChild(opt);
            sel.value = data.customer.id;
            onCustomerChange();
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

    return render_template_string(page_wrapper('首页报价器 - 新一骏纸品有限公司', 'home', content, page_js))


# ============================================================
#  路由：AJAX 保存报价（/api/quote/save）
# ============================================================
@app.route('/api/quote/save', methods=['POST'])
def api_save_quote():
    rules = load_rules()
    customers = load_customers()

    try:
        customer_id = int(request.form.get('customer_id', 0)) if request.form.get('customer_id') else 0
        material_id = int(request.form.get('material_id', 0))
        length = float(request.form.get('length', 0))
        width = float(request.form.get('width', 0))
        height = float(request.form.get('height', 0))
        quantity = int(request.form.get('quantity', 0))
        unit = request.form.get('unit', 'cm')
        remark = request.form.get('remark', '').strip()
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': '请输入有效的数字'})

    material = None
    for r in rules:
        if r['id'] == material_id:
            material = r
            break

    if not material:
        return jsonify({'success': False, 'message': '请选择有效的材质'})
    if not customer_id:
        return jsonify({'success': False, 'message': '请先选择客户'})
    if length <= 0 or width <= 0 or quantity <= 0:
        return jsonify({'success': False, 'message': '请输入有效的尺寸和数量'})

    # 查找客户
    customer_name = ''
    for c in customers:
        if c['id'] == customer_id:
            customer_name = c['name']
            break

    # 计算价格
    unit_factor = {'mm': 0.1, 'cm': 1.0, 'm': 100.0}.get(unit, 1.0)
    length_cm = length * unit_factor
    width_cm = width * unit_factor
    len_add = material['length_addition']
    wid_add = material['width_addition']
    unit_price = material['unit_price']
    area = (length_cm + len_add) * (width_cm + wid_add) * 2 * quantity
    original_total = area * unit_price

    discounts = material.get('discounts', [])
    applicable = [d for d in discounts if d['min_qty'] <= quantity]
    has_discount = False
    discount_rate = None
    if applicable:
        best = max(applicable, key=lambda d: d['min_qty'])
        discount_rate = best['discount_rate']
        final_total = original_total * discount_rate
        has_discount = True
    else:
        final_total = original_total

    # 生成编号并保存
    all_quotes = load_quotes()
    quote_no = generate_quote_no(all_quotes)
    new_quote_id = get_next_id(all_quotes)
    quote_record = {
        'id': new_quote_id,
        'quote_no': quote_no,
        'customer_id': customer_id,
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
    all_quotes.append(quote_record)
    save_quotes(all_quotes)

    return jsonify({
        'success': True,
        'quote_no': quote_no,
        'quote_id': new_quote_id,
        'final_total': round(final_total, 2)
    })


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
              <td><a href="/quotes/print/{q['id']}" target="_blank" class="btn-link" style="color:#8B5A2B;margin-right:8px;">打印</a><a href="/quotes/delete/{q['id']}" class="btn-link-del" onclick="return confirm('确认删除报价单「{q_no}」？')">删除</a></td>
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


# ============================================================
#  路由：报价单打印页（/quotes/print/<qid>）
# ============================================================
@app.route('/quotes/print/<int:qid>')
def print_quote_page(qid):
    quotes = load_quotes()
    quote = None
    for q in quotes:
        if q['id'] == qid:
            quote = q
            break
    if not quote:
        return '<h3>报价单不存在</h3>', 404

    # 查客户信息
    customers = load_customers()
    cust = None
    cid = quote.get('customer_id')
    if cid:
        for c in customers:
            if c['id'] == cid:
                cust = c
                break

    cust_name = quote.get('customer_name', '') or (cust['name'] if cust else '')
    cust_phone = cust.get('phone', '') if cust else ''
    cust_company = cust.get('company', '') if cust else ''
    cust_address = cust.get('address', '') if cust else ''

    q_no = quote.get('quote_no', f'QJ{quote["id"]:08d}')
    created = quote.get('created_at', '')
    mat_name = quote.get('material_name', '')
    q_unit = quote.get('input_unit', 'cm')
    disc_desc = quote.get('discount_desc', '')
    disc_rate = quote.get('discount_rate')
    remark = quote.get('remark', '') or ''

    html = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>报价单 {q_no}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Microsoft YaHei','SimHei',sans-serif; color:#333; padding:40px; max-width:780px; margin:0 auto; }}
  .doc-header {{ text-align:center; border-bottom:3px double #8B5A2B; padding-bottom:20px; margin-bottom:24px; }}
  .doc-header h1 {{ font-size:26px; color:#8B5A2B; margin-bottom:6px; letter-spacing:2px; }}
  .doc-header .contact {{ font-size:13px; color:#999; }}
  .doc-bar {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; }}
  .doc-bar .qno {{ font-size:18px; color:#8B5A2B; font-weight:700; }}
  .doc-bar .date {{ font-size:13px; color:#888; }}
  .doc-title {{ font-size:15px; color:#8B5A2B; font-weight:bold; border-left:4px solid #8B5A2B; padding-left:8px; margin:20px 0 10px; }}
  table.info {{ width:100%; border-collapse:collapse; margin-bottom:8px; }}
  table.info td {{ padding:7px 12px; border:1px solid #e8e0d5; font-size:14px; }}
  table.info td.label {{ width:110px; color:#8B7355; background:#faf8f5; font-weight:500; }}
  .two-col {{ display:flex; gap:16px; }}
  .two-col > div {{ flex:1; }}
  table.detail {{ width:100%; border-collapse:collapse; margin-bottom:8px; }}
  table.detail th {{ background:#8B5A2B; color:#fff; padding:8px; font-size:13px; font-weight:500; text-align:left; }}
  table.detail td {{ padding:8px 12px; border:1px solid #e0d5c8; font-size:14px; }}
  .total-bar {{ display:flex; justify-content:flex-end; margin:12px 0; }}
  .total-bar .total-box {{ background:#fdf5e6; border:2px solid #8B5A2B; border-radius:8px; padding:10px 28px; text-align:center; }}
  .total-bar .total-box .lbl {{ font-size:13px; color:#8B7355; }}
  .total-bar .total-box .val {{ font-size:24px; color:#8B5A2B; font-weight:700; }}
  .total-bar .total-box .val .y {{ font-size:14px; }}
  .remark-area {{ background:#faf8f5; border:1px solid #e0d5c8; border-radius:6px; padding:12px 16px; margin:16px 0; font-size:14px; color:#5a5045; }}
  .remark-area .rm-lbl {{ color:#8B5A2B; font-weight:bold; margin-right:8px; }}
  .sign-area {{ display:flex; justify-content:space-between; margin-top:50px; padding-top:20px; }}
  .sign-box {{ text-align:center; }}
  .sign-box .sign-line {{ width:200px; border-bottom:1px solid #999; margin-bottom:6px; }}
  .sign-box .sign-lbl {{ font-size:13px; color:#888; }}
  .doc-footer {{ text-align:center; margin-top:36px; padding-top:14px; border-top:1px solid #eee; font-size:12px; color:#bbb; }}
  @media print {{ body {{ padding:20px; }} .no-print {{ display:none; }} }}
  .print-btn {{ position:fixed; top:20px; right:20px; padding:10px 24px; background:#8B5A2B; color:#fff; border:none; border-radius:8px; font-size:14px; cursor:pointer; }}
  .print-btn:hover {{ background:#6B4423; }}
</style></head><body>
  <button class="print-btn no-print" onclick="window.print()">🖨️ 打印</button>
  <div class="doc-header">
    <h1>{COMPANY_NAME}</h1>
    <div class="contact">地址：{COMPANY_ADDRESS}　｜　电话：{COMPANY_PHONE}</div>
  </div>

  <div class="doc-bar">
    <div class="qno">{q_no}</div>
    <div class="date">制单日期：{created[:10] if created else ''}</div>
  </div>

  <div class="two-col">
    <div>
      <div class="doc-title">客户信息</div>
      <table class="info">
        <tr><td class="label">客户名称</td><td>{cust_name}</td></tr>
        <tr><td class="label">联系电话</td><td>{cust_phone or '—'}</td></tr>
        <tr><td class="label">公司名称</td><td>{cust_company or '—'}</td></tr>
        <tr><td class="label">送货地址</td><td>{cust_address or '—'}</td></tr>
      </table>
    </div>
    <div>
      <div class="doc-title">报价概况</div>
      <table class="info">
        <tr><td class="label">选用材质</td><td>{mat_name}</td></tr>
        <tr><td class="label">输入尺寸</td><td>{quote['length']:.1f} × {quote['width']:.1f} × {quote['height']:.1f} {q_unit}</td></tr>
        <tr><td class="label">数量</td><td>{quote['quantity']} 个</td></tr>
        <tr><td class="label">报价时间</td><td>{created}</td></tr>
      </table>
    </div>
  </div>

  <div class="doc-title">价格明细</div>
  <table class="detail">
    <tr><th>项目</th><th>数值</th></tr>
    <tr><td>用料面积</td><td>{quote.get('area', 0):.2f} 平方厘米</td></tr>
    <tr><td>纸质单价</td><td>{quote.get('unit_price', 0):.6f} 元/平方厘米</td></tr>
    <tr><td>原始总价</td><td>{quote.get('original_total', 0):.2f} 元</td></tr>
    <tr><td>优惠信息</td><td>{f'{disc_desc}（省 {quote.get("original_total", 0) - quote.get("final_total", 0):.2f} 元）' if disc_rate else '无优惠'}</td></tr>
  </table>

  <div class="total-bar">
    <div class="total-box">
      <div class="lbl">最终应付总价</div>
      <div class="val">{quote.get('final_total', 0):.2f}<span class="y"> 元</span></div>
    </div>
  </div>

  {f'<div class="remark-area"><span class="rm-lbl">备注</span>{remark}</div>' if remark else ''}

  <div class="sign-area">
    <div class="sign-box">
      <div class="sign-line"></div>
      <div class="sign-lbl">供方签字（盖章）</div>
    </div>
    <div class="sign-box">
      <div class="sign-line"></div>
      <div class="sign-lbl">客户签字确认</div>
    </div>
  </div>

  <div class="doc-footer">本报价单自制单日起30天内有效 · {COMPANY_NAME}</div>

  <script>window.onload = function() {{ setTimeout(function() {{ window.print(); }}, 500); }};</script>
</body></html>"""
    return html


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
    # 日常使用关闭 debug，避免 reloader 产生僵尸子进程导致端口占用
    debug_mode = os.environ.get('FLASK_DEBUG') == '1'
    print("=" * 50)
    print("  新一骏纸品有限公司 - 智能报价系统")
    print(f"  访问地址: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
