import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from supabase import create_client, Client
import os

# ==================== 必须在所有 Streamlit 命令之前 ====================
st.set_page_config(page_title="中药学院试剂管理系统", layout="wide")

# ==================== Supabase 客户端初始化 ====================
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# ==================== 演示数据初始化 ====================
def init_demo_data():
    """如果 reagents 表为空，插入演示数据"""
    resp = supabase.table("reagents").select("id").limit(1).execute()
    if len(resp.data) == 0:
        now = datetime.now(timezone.utc).isoformat()
        demo_reagents = [
            {
                "code": "R001",
                "name": "无水乙醇",
                "cas_no": "64-17-5",
                "specification": "500ml/瓶",
                "unit": "瓶",
                "stock": 50,
                "min_stock": 10,
                "max_stock": 100,
                "location": "试剂柜A1",
                "created_at": now,
                "updated_at": now,
            },
            {
                "code": "R002",
                "name": "甲醇",
                "cas_no": "67-56-1",
                "specification": "HPLC 4L",
                "unit": "桶",
                "stock": 8,
                "min_stock": 2,
                "max_stock": 20,
                "location": "通风橱B2",
                "created_at": now,
                "updated_at": now,
            },
            {
                "code": "R003",
                "name": "乙酸乙酯",
                "cas_no": "141-78-6",
                "specification": "500ml/瓶",
                "unit": "瓶",
                "stock": 30,
                "min_stock": 5,
                "max_stock": 60,
                "location": "试剂柜A2",
                "created_at": now,
                "updated_at": now,
            },
        ]
        for reagent in demo_reagents:
            supabase.table("reagents").insert(reagent).execute()

        # 获取刚插入的试剂 ID 并添加交易记录
        resp = supabase.table("reagents").select("id, code").execute()
        id_map = {row["code"]: row["id"] for row in resp.data}
        demo_trans = [
            {
                "reagent_id": id_map["R001"],
                "type": "in",
                "quantity": 20,
                "operator": "张老师",
                "remark": "新采购",
                "timestamp": now,
            },
            {
                "reagent_id": id_map["R001"],
                "type": "out",
                "quantity": 5,
                "operator": "李同学",
                "remark": "实验教学",
                "timestamp": now,
            },
            {
                "reagent_id": id_map["R002"],
                "type": "in",
                "quantity": 5,
                "operator": "王老师",
                "remark": "补充库存",
                "timestamp": now,
            },
        ]
        for trans in demo_trans:
            supabase.table("transactions").insert(trans).execute()

# ==================== 辅助函数 ====================
def get_reagents():
    """获取所有试剂，返回DataFrame"""
    response = supabase.table("reagents").select("*").order("code").execute()
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame()
    return df

def get_transactions(start_date=None, end_date=None, reagent_id=None):
    """根据条件获取交易记录"""
    query = supabase.table("transactions").select(
        "id, timestamp, reagent_id, type, quantity, operator, remark, reagents!inner(code, name)"
    )
    if start_date:
        query = query.gte("timestamp", start_date.isoformat())
    if end_date:
        query = query.lte("timestamp", end_date.isoformat())
    if reagent_id:
        query = query.eq("reagent_id", reagent_id)
    query = query.order("timestamp", desc=True)
    response = query.execute()
    data = response.data
    # 展开reagents信息
    for row in data:
        row["code"] = row["reagents"]["code"]
        row["name"] = row["reagents"]["name"]
        del row["reagents"]
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame()
    return df

def add_reagent(code, name, cas_no, spec, unit, stock, min_stock, max_stock, location):
    now = datetime.now(timezone.utc).isoformat()
    try:
        supabase.table("reagents").insert({
            "code": code,
            "name": name,
            "cas_no": cas_no,
            "specification": spec,
            "unit": unit,
            "stock": stock,
            "min_stock": min_stock,
            "max_stock": max_stock,
            "location": location,
            "created_at": now,
            "updated_at": now
        }).execute()
        st.success("试剂添加成功")
    except Exception as e:
        if "duplicate key value violates unique constraint" in str(e):
            st.error("试剂编号已存在，请使用唯一编号")
        else:
            st.error(f"添加失败：{e}")

def update_reagent(id, code, name, cas_no, spec, unit, stock, min_stock, max_stock, location):
    now = datetime.now(timezone.utc).isoformat()
    try:
        supabase.table("reagents").update({
            "code": code,
            "name": name,
            "cas_no": cas_no,
            "specification": spec,
            "unit": unit,
            "stock": stock,
            "min_stock": min_stock,
            "max_stock": max_stock,
            "location": location,
            "updated_at": now
        }).eq("id", id).execute()
        st.success("试剂信息更新成功")
    except Exception as e:
        if "duplicate key value violates unique constraint" in str(e):
            st.error("试剂编号与其他记录冲突")
        else:
            st.error(f"更新失败：{e}")

def delete_reagent(id):
    # 检查是否有交易记录
    trans_resp = supabase.table("transactions").select("id").eq("reagent_id", id).execute()
    if len(trans_resp.data) > 0:
        st.error("该试剂存在出入库记录，无法删除")
        return
    # 检查库存
    reagent_resp = supabase.table("reagents").select("stock").eq("id", id).execute()
    if reagent_resp.data and reagent_resp.data[0]["stock"] != 0:
        st.error("当前库存不为0，请先处理库存后再删除")
        return
    supabase.table("reagents").delete().eq("id", id).execute()
    st.success("试剂已删除")

def stock_change(reagent_id, change_type, quantity, operator, remark):
    # 获取当前库存
    resp = supabase.table("reagents").select("name, unit, stock").eq("id", reagent_id).execute()
    if not resp.data:
        st.error("试剂不存在")
        return False
    row = resp.data[0]
    name, unit, current_stock = row["name"], row["unit"], row["stock"]
    quantity = int(quantity)

    if change_type == 'out' and current_stock < quantity:
        st.error(f"库存不足！当前库存 {current_stock}{unit}，出库 {quantity}{unit} 失败")
        return False

    new_stock = current_stock + quantity if change_type == 'in' else current_stock - quantity

    # 更新库存
    supabase.table("reagents").update({"stock": new_stock}).eq("id", reagent_id).execute()
    # 添加交易记录
    supabase.table("transactions").insert({
        "reagent_id": reagent_id,
        "type": change_type,
        "quantity": quantity,
        "operator": operator,
        "remark": remark,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }).execute()
    st.success(f"试剂 {name} {('入库' if change_type=='in' else '出库')} {quantity}{unit} 成功")
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
    if not df.empty and search:
        df = df[df.apply(lambda row: search.lower() in str(row['code']).lower() or 
                                   search.lower() in str(row['name']).lower() or 
                                   search.lower() in str(row['cas_no']).lower(), axis=1)]

    if df.empty:
        st.info("暂无试剂数据")
        return

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
            reagents_df = get_reagents()
            if not reagents_df.empty:
                reagent_options = {"全部": None}
                for _, row in reagents_df.iterrows():
                    reagent_options[f"{row['name']} (ID:{row['id']})"] = row['id']
                selected_reagent = st.selectbox("选择试剂", list(reagent_options.keys()), key="reagent_filter")
                reagent_id = reagent_options[selected_reagent]
            else:
                selected_reagent = "全部"
                reagent_id = None
        search = st.text_input("快速搜索（试剂名称/编号/操作人）", placeholder="输入关键词...")
        apply_filter = st.button("应用筛选")

    if 'filtered_df' not in st.session_state or apply_filter:
        df = get_transactions(start_date, end_date, reagent_id)
        if not df.empty and search:
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
    health_check()
    if not check_password():
        return

    # 初始化演示数据（如果表为空）
    init_demo_data()

    st.sidebar.title("导航")
    page = st.sidebar.radio("功能选择", ["库存管理", "出入库记录"])
    if page == "库存管理":
        show_inventory()
    else:
        show_transactions()

if __name__ == "__main__":
    main()
