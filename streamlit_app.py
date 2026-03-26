import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

# ==================== 必须在所有 Streamlit 命令之前 ====================
st.set_page_config(page_title="中药学院试剂管理系统", layout="wide")

# ==================== 数据库初始化 ====================
DB_PATH = "reagent.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 试剂表
    c.execute('''CREATE TABLE IF NOT EXISTS reagents
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  code TEXT UNIQUE,
                  name TEXT,
                  cas_no TEXT,
                  specification TEXT,
                  unit TEXT,
                  stock INTEGER,
                  min_stock INTEGER,
                  max_stock INTEGER,
                  location TEXT,
                  created_at TEXT,
                  updated_at TEXT)''')
    # 交易记录表
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  reagent_id INTEGER,
                  type TEXT,
                  quantity INTEGER,
                  operator TEXT,
                  remark TEXT,
                  timestamp TEXT,
                  FOREIGN KEY(reagent_id) REFERENCES reagents(id))''')
    # 插入演示数据（若为空）
    c.execute("SELECT COUNT(*) FROM reagents")
    if c.fetchone()[0] == 0:
        demo_reagents = [
            ('R001', '无水乙醇', '64-17-5', '500ml/瓶', '瓶', 50, 10, 100, '试剂柜A1', datetime.now().isoformat(), datetime.now().isoformat()),
            ('R002', '甲醇', '67-56-1', 'HPLC 4L', '桶', 8, 2, 20, '通风橱B2', datetime.now().isoformat(), datetime.now().isoformat()),
            ('R003', '乙酸乙酯', '141-78-6', '500ml/瓶', '瓶', 30, 5, 60, '试剂柜A2', datetime.now().isoformat(), datetime.now().isoformat()),
        ]
        c.executemany("INSERT INTO reagents (code,name,cas_no,specification,unit,stock,min_stock,max_stock,location,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", demo_reagents)
        conn.commit()
        # 示例交易记录
        c.execute("SELECT id FROM reagents WHERE code='R001'")
        r1 = c.fetchone()[0]
        c.execute("SELECT id FROM reagents WHERE code='R002'")
        r2 = c.fetchone()[0]
        demo_trans = [
            (r1, 'in', 20, '张老师', '新采购', datetime.now().isoformat()),
            (r1, 'out', 5, '李同学', '实验教学', datetime.now().isoformat()),
            (r2, 'in', 5, '王老师', '补充库存', datetime.now().isoformat()),
        ]
        c.executemany("INSERT INTO transactions (reagent_id,type,quantity,operator,remark,timestamp) VALUES (?,?,?,?,?,?)", demo_trans)
        conn.commit()
    conn.close()

# ==================== 辅助函数 ====================
def get_reagents():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM reagents ORDER BY code", conn)
    conn.close()
    return df

def get_transactions(start_date=None, end_date=None, reagent_id=None):
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT t.id, t.timestamp, r.code, r.name, t.type, t.quantity, t.operator, t.remark
        FROM transactions t
        LEFT JOIN reagents r ON t.reagent_id = r.id
        WHERE 1=1
    """
    params = []
    if start_date:
        query += " AND date(t.timestamp) >= ?"
        params.append(start_date.isoformat())
    if end_date:
        query += " AND date(t.timestamp) <= ?"
        params.append(end_date.isoformat())
    if reagent_id:
        query += " AND t.reagent_id = ?"
        params.append(reagent_id)
    query += " ORDER BY t.timestamp DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def add_reagent(code, name, cas_no, spec, unit, stock, min_stock, max_stock, location):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute("INSERT INTO reagents (code,name,cas_no,specification,unit,stock,min_stock,max_stock,location,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (code, name, cas_no, spec, unit, stock, min_stock, max_stock, location, now, now))
        conn.commit()
        st.success("试剂添加成功")
    except sqlite3.IntegrityError:
        st.error("试剂编号已存在，请使用唯一编号")
    conn.close()

def update_reagent(id, code, name, cas_no, spec, unit, stock, min_stock, max_stock, location):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute("UPDATE reagents SET code=?, name=?, cas_no=?, specification=?, unit=?, stock=?, min_stock=?, max_stock=?, location=?, updated_at=? WHERE id=?",
                  (code, name, cas_no, spec, unit, stock, min_stock, max_stock, location, now, id))
        conn.commit()
        st.success("试剂信息更新成功")
    except sqlite3.IntegrityError:
        st.error("试剂编号与其他记录冲突")
    conn.close()

def delete_reagent(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 检查是否有交易记录
    c.execute("SELECT COUNT(*) FROM transactions WHERE reagent_id=?", (id,))
    if c.fetchone()[0] > 0:
        st.error("该试剂存在出入库记录，无法删除")
        conn.close()
        return
    c.execute("SELECT stock FROM reagents WHERE id=?", (id,))
    stock = c.fetchone()[0]
    if stock != 0:
        st.error("当前库存不为0，请先处理库存后再删除")
        conn.close()
        return
    c.execute("DELETE FROM reagents WHERE id=?", (id,))
    conn.commit()
    st.success("试剂已删除")
    conn.close()

def stock_change(reagent_id, change_type, quantity, operator, remark):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 获取试剂信息
    c.execute("SELECT name, unit, stock FROM reagents WHERE id=?", (reagent_id,))
    row = c.fetchone()
    if not row:
        st.error("试剂不存在")
        conn.close()
        return False
    name, unit, current_stock = row
    quantity = int(quantity)
    if change_type == 'out' and current_stock < quantity:
        st.error(f"库存不足！当前库存 {current_stock}{unit}，出库 {quantity}{unit} 失败")
        conn.close()
        return False
    new_stock = current_stock + quantity if change_type == 'in' else current_stock - quantity
    c.execute("UPDATE reagents SET stock=? WHERE id=?", (new_stock, reagent_id))
    c.execute("INSERT INTO transactions (reagent_id, type, quantity, operator, remark, timestamp) VALUES (?,?,?,?,?,?)",
              (reagent_id, change_type, quantity, operator, remark, datetime.now().isoformat()))
    conn.commit()
    st.success(f"试剂 {name} {('入库' if change_type=='in' else '出库')} {quantity}{unit} 成功")
    conn.close()
    return True

# ==================== 登录验证 ====================
def check_password():
    """返回 True 表示已登录，False 表示未登录"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("试剂出入库管理系统")
    st.write("请输入用户名和密码")
    username = st.text_input("用户名")
    password = st.text_input("密码", type="password")
    if st.button("登录"):
        if username == "ZY" and password == "513513":
            st.session_state.authenticated = True
            st.success("登录成功")
            st.rerun()
        else:
            st.error("用户名或密码错误")
    return False

# ==================== 健康检查（可选）====================
def health_check():
    # 兼容旧版 Streamlit
    try:
        params = st.query_params
    except AttributeError:
        params = st.experimental_get_query_params()
    if params.get("health") == ["1"]:
        st.write("OK")
        st.stop()

# ==================== 库存管理页面 ====================
def show_inventory():
    st.header("📦 试剂库存管理")
    col1, col2 = st.columns([3, 1])
    with col1:
        search = st.text_input("搜索试剂名称/编号/CAS", placeholder="输入关键词...")
    with col2:
        st.markdown("")
        if st.button("🔄 刷新列表"):
            st.rerun()

    df = get_reagents()
    if search:
        df = df[df.apply(lambda row: search.lower() in str(row['code']).lower() or 
                                   search.lower() in str(row['name']).lower() or 
                                   search.lower() in str(row['cas_no']).lower(), axis=1)]

    # 显示表格
    display_df = df[['id', 'code', 'name', 'cas_no', 'specification', 'unit', 'stock', 'min_stock', 'max_stock', 'location']].copy()
    display_df.columns = ['ID', '编号', '名称', 'CAS号', '规格', '单位', '库存', '预警下限', '预警上限', '存放位置']

    # 高亮预警
    def highlight_warning(row):
        if row['库存'] <= row['预警下限'] and row['预警下限'] > 0:
            return ['background-color: #fff3cd'] * len(row)
        elif row['库存'] >= row['预警上限'] and row['预警上限'] > 0:
            return ['background-color: #f8d7da'] * len(row)
        else:
            return [''] * len(row)

    styled_df = display_df.style.apply(highlight_warning, axis=1)
    st.dataframe(styled_df, use_container_width=True)

    # 操作区域
    st.subheader("✏️ 试剂操作")
    tab1, tab2, tab3, tab4 = st.tabs(["入库", "出库", "添加试剂", "编辑/删除"])

    with tab1:
        with st.form("in_form"):
            reagents = df[['id', 'name']].to_dict('records')
            reagent_options = {f"{r['name']} (ID:{r['id']})": r['id'] for r in reagents}
            selected = st.selectbox("选择试剂", list(reagent_options.keys()))
            quantity = st.number_input("入库数量", min_value=1, step=1)
            operator = st.text_input("操作人")
            remark = st.text_area("备注")
            submitted = st.form_submit_button("确认入库")
            if submitted:
                if not operator:
                    st.error("请填写操作人")
                else:
                    stock_change(reagent_options[selected], 'in', quantity, operator, remark)
                    st.rerun()

    with tab2:
        with st.form("out_form"):
            reagents = df[['id', 'name', 'stock']].to_dict('records')
            reagent_options = {f"{r['name']} (库存:{r['stock']})": r['id'] for r in reagents}
            selected = st.selectbox("选择试剂", list(reagent_options.keys()))
            quantity = st.number_input("出库数量", min_value=1, step=1)
            operator = st.text_input("操作人")
            remark = st.text_area("备注")
            submitted = st.form_submit_button("确认出库")
            if submitted:
                if not operator:
                    st.error("请填写操作人")
                else:
                    stock_change(reagent_options[selected], 'out', quantity, operator, remark)
                    st.rerun()

    with tab3:
        with st.form("add_form"):
            code = st.text_input("试剂编号 *")
            name = st.text_input("试剂名称 *")
            col1, col2 = st.columns(2)
            with col1:
                cas_no = st.text_input("CAS号")
                unit = st.text_input("单位", value="瓶")
                stock = st.number_input("初始库存", min_value=0, step=1, value=0)
            with col2:
                specification = st.text_input("规格")
                min_stock = st.number_input("最低库存预警", min_value=0, step=1, value=0)
                max_stock = st.number_input("最高库存限制", min_value=0, step=1, value=0)
            location = st.text_input("存放位置")
            submitted = st.form_submit_button("添加试剂")
            if submitted:
                if not code or not name:
                    st.error("试剂编号和名称不能为空")
                else:
                    add_reagent(code, name, cas_no, specification, unit, stock, min_stock, max_stock, location)
                    st.rerun()

    with tab4:
        if df.empty:
            st.info("暂无试剂")
        else:
            reagent_id = st.selectbox("选择要编辑或删除的试剂", options=df['id'].tolist(), format_func=lambda x: f"{df[df['id']==x]['name'].values[0]} ({df[df['id']==x]['code'].values[0]})")
            if reagent_id:
                row = df[df['id'] == reagent_id].iloc[0]
                with st.form("edit_form"):
                    code = st.text_input("编号", value=row['code'])
                    name = st.text_input("名称", value=row['name'])
                    col1, col2 = st.columns(2)
                    with col1:
                        cas_no = st.text_input("CAS号", value=row['cas_no'] or '')
                        unit = st.text_input("单位", value=row['unit'])
                        stock = st.number_input("当前库存", value=int(row['stock']), min_value=0)
                    with col2:
                        specification = st.text_input("规格", value=row['specification'] or '')
                        min_stock = st.number_input("最低库存", value=int(row['min_stock']), min_value=0)
                        max_stock = st.number_input("最高库存", value=int(row['max_stock']), min_value=0)
                    location = st.text_input("存放位置", value=row['location'] or '')
                    col_a, col_b = st.columns(2)
                    with col_a:
                        submitted = st.form_submit_button("保存修改")
                    with col_b:
                        delete_btn = st.form_submit_button("删除试剂")
                    if submitted:
                        update_reagent(reagent_id, code, name, cas_no, specification, unit, stock, min_stock, max_stock, location)
                        st.rerun()
                    if delete_btn:
                        delete_reagent(reagent_id)
                        st.rerun()

    # 打印按钮
    if st.button("🖨️ 打印库存清单"):
        html_table = display_df.to_html(index=False, classes='table table-bordered table-striped', escape=False)
        print_html = f"""
        <html>
        <head>
            <title>试剂库存清单</title>
            <style>
                body {{ font-family: 'SimHei', 'Microsoft YaHei', sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 20px; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                @media print {{
                    .no-print {{ display: none; }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>上海中医药大学中药学院实验教学中心</h2>
                <p>试剂库存清单</p>
                <p>打印时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            {html_table}
            <div class="footer">
                <p>系统生成，仅供参考</p>
            </div>
            <script>
                window.onload = function() {{ window.print(); }};
            </script>
        </body>
        </html>
        """
        st.components.v1.html(print_html, height=0, scrolling=False)

# ==================== 出入库记录页面 ====================
def show_transactions():
    st.header("📜 出入库流水记录")

    # 高级筛选
    with st.expander("🔍 高级筛选（可选）", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            start_date = st.date_input("起始日期", value=None, key="start_date")
        with col2:
            end_date = st.date_input("结束日期", value=None, key="end_date")
        with col3:
            conn = sqlite3.connect(DB_PATH)
            reagents_df = pd.read_sql_query("SELECT id, name FROM reagents ORDER BY name", conn)
            conn.close()
            reagent_options = {"全部": None}
            for _, row in reagents_df.iterrows():
                reagent_options[f"{row['name']} (ID:{row['id']})"] = row['id']
            selected_reagent = st.selectbox("选择试剂", list(reagent_options.keys()), key="reagent_filter")
            reagent_id = reagent_options[selected_reagent]
        search = st.text_input("快速搜索（试剂名称/编号/操作人）", placeholder="输入关键词...")
        apply_filter = st.button("应用筛选")

    if 'filtered_df' not in st.session_state or apply_filter:
        df = get_transactions(start_date, end_date, reagent_id)
        if search:
            df = df[df.apply(lambda row: search.lower() in str(row['name']).lower() or 
                                       search.lower() in str(row['code']).lower() or 
                                       search.lower() in str(row['operator']).lower(), axis=1)]
        st.session_state.filtered_df = df
    else:
        df = st.session_state.filtered_df

    if df.empty:
        st.info("暂无符合条件的交易记录")
        return

    # 显示表格
    display_df = df[['timestamp', 'code', 'name', 'type', 'quantity', 'operator', 'remark']].copy()
    display_df.columns = ['时间', '试剂编号', '试剂名称', '类型', '数量', '操作人', '备注']
    display_df['类型'] = display_df['类型'].map({'in': '入库', 'out': '出库'})
    st.dataframe(display_df, use_container_width=True)

    # 打印按钮
    if st.button("🖨️ 打印当前筛选结果"):
        filter_desc = []
        if start_date:
            filter_desc.append(f"起始日期：{start_date}")
        if end_date:
            filter_desc.append(f"结束日期：{end_date}")
        if selected_reagent != "全部":
            filter_desc.append(f"试剂：{selected_reagent}")
        if search:
            filter_desc.append(f"关键词：{search}")
        filter_text = "；".join(filter_desc) if filter_desc else "无筛选条件"

        html_table = display_df.to_html(index=False, classes='table table-bordered table-striped', escape=False)
        print_html = f"""
        <html>
        <head>
            <title>出入库记录</title>
            <style>
                body {{ font-family: 'SimHei', 'Microsoft YaHei', sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 20px; }}
                .filter-info {{ margin-bottom: 15px; padding: 8px; background-color: #f5f5f5; border-left: 4px solid #0d6efd; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                @media print {{
                    .no-print {{ display: none; }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>上海中医药大学中药学院实验教学中心</h2>
                <p>试剂出入库记录</p>
                <p>打印时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            <div class="filter-info">
                <strong>当前筛选条件：</strong> {filter_text}
            </div>
            {html_table}
            <div class="footer">
                <p>系统生成，仅供参考</p>
            </div>
            <script>
                window.onload = function() {{ window.print(); }};
            </script>
        </body>
        </html>
        """
        st.components.v1.html(print_html, height=0, scrolling=False)

# ==================== 主程序 ====================
def main():
    init_db()
    health_check()          # 健康检查，必须在 st.set_page_config 之后
    if not check_password():
        return

    st.sidebar.title("导航")
    page = st.sidebar.radio("功能选择", ["库存管理", "出入库记录"])
    if page == "库存管理":
        show_inventory()
    else:
        show_transactions()

if __name__ == "__main__":
    main()
