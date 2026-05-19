import streamlit as st
import pandas as pd
import sqlite3
import datetime
import requests
import os

# --- 1. 설정 및 데이터베이스 초기화 ---
TELEGRAM_TOKEN = '8719449602:AAFSP1W-vdaaIw4fXVSkGEeoG47me-qj9_o' 
TELEGRAM_CHAT_ID = '8262814335' 

def send_telegram_msg(message):
    """주문 발생 시 텔레그램으로 알림 전송"""
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        try:
            requests.get(url, params=params, timeout=5)
        except Exception as e:
            print(f"텔레그램 전송 실패: {e}")

def get_connection():
    return sqlite3.connect('business_data.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS clients 
                    (client_id TEXT PRIMARY KEY, password TEXT, client_name TEXT, target_tier TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_date TEXT,
                        client_name TEXT,
                        item_name TEXT,
                        spec TEXT,
                        unit TEXT,
                        price INTEGER,
                        qty INTEGER,
                        total INTEGER,
                        status TEXT DEFAULT '신규주문'
                    )''')
    conn.commit()
    conn.close()

# --- [신규 기능] 깃허브에 올린 엑셀 파일이 있다면 자동으로 DB에 로드하는 함수 ---
def auto_load_git_files():
    conn = get_connection()
    
    # 1. 단가표 자동 로드
    try:
        # products 테이블이 없거나 데이터가 0개일 때만 실행
        tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' AND name='products'", conn)
        if tables.empty or pd.read_sql("SELECT count(*) FROM products", conn).iloc[0, 0] == 0:
            if os.path.exists('price_list.xlsx'):
                df_p = process_price_excel('price_list.xlsx')
                df_p.to_sql('products', conn, if_exists='replace', index=False)
    except Exception as e:
        print(f"단가표 자동 로드 실패: {e}")

    # 2. 거래처 목록 자동 로드
    try:
        # clients 테이블에 데이터가 0개일 때만 실행 (최초 초기화인 경우)
        client_count = pd.read_sql("SELECT count(*) FROM clients", conn).iloc[0, 0]
        if client_count == 0:
            if os.path.exists('client_list.xlsx'):
                df_c = process_client_excel('client_list.xlsx')
                df_c.to_sql('clients', conn, if_exists='replace', index=False)
    except Exception as e:
        print(f"거래처 자동 로드 실패: {e}")
        
    conn.close()

# --- 2. 관리자 로직 (엑셀 처리) ---
def process_price_excel(file):
    df = pd.read_excel(file, header=[0, 1])
    new_cols = []
    for col in df.columns:
        p1 = str(col[0]) if "Unnamed" not in str(col[0]) else ""
        p2 = str(col[1]) if "Unnamed" not in str(col[1]) else ""
        new_cols.append(f"{p1}_{p2}".strip("_") if p1 and p2 else (p1 or p2))
    df.columns = [c.strip() for c in new_cols]
    price_cols = [c for c in df.columns if "_계산값" in c]
    base_cols = ['코드', '상품명', '규격', '단위']
    valid_base = [c for c in base_cols if c in df.columns]
    final_df = df[valid_base + price_cols]
    final_df.columns = [c.replace("_계산값", "") for c in final_df.columns]
    return final_df

def process_client_excel(file):
    df = pd.read_excel(file, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    col_map = {'코드': 'client_id', '상호명': 'client_name', '적용단가': 'target_tier'}
    available = [c for c in col_map.keys() if c in df.columns]
    client_df = df[available].rename(columns=col_map)
    client_df['client_id'] = client_df['client_id'].apply(lambda x: str(x).split('.')[0].strip())
    client_df['password'] = '1234'
    client_df['client_name'] = client_df['client_name'].str.strip()
    client_df['target_tier'] = client_df['target_tier'].str.strip()
    return client_df

# --- 3. 메인 화면 ---
def main():
    st.set_page_config(page_title="자재 발주 시스템", layout="wide")
    init_db()
    auto_load_git_files()  # [신규 부품] 프로그램 시작 시 엑셀 파일 존재하면 자동 파싱

    if 'is_logged_in' not in st.session_state:
        st.session_state.is_logged_in = False
    if 'user_info' not in st.session_state:
        st.session_state.user_info = None

    menu = st.sidebar.radio("메뉴 선택", ["거래처 로그인", "관리자 모드"])

    # --- 관리자 모드 ---
    if menu == "관리자 모드":
        st.header("⚙️ 관리자 업무 제어 센터")
        admin_pw = st.text_input("관리자 암호", type="password")
        
        if admin_pw == "admin1234":
            t1, t2, t3 = st.tabs(["1. 단가표 업로드", "2. 거래처 업로드", "3. 주문 현황 관리"])
            
            with t1:
                st.info("💡 팁: 'price_list.xlsx' 파일명으로 깃허브에 올려두시면 매번 업로드할 필요 없이 항상 자동 유지됩니다.")
                f1 = st.file_uploader("천년경영 '자재단가' 엑셀 수동 업로드", type=["xlsx"], key="admin_p_up")
                if f1 and st.button("단가표 DB 반영"):
                    df_p = process_price_excel(f1)
                    conn = get_connection()
                    df_p.to_sql('products', conn, if_exists='replace', index=False)
                    conn.close()
                    st.success("✅ 상품별 단가 정보가 업데이트되었습니다!")
                
                # 상시 미리보기 연동
                conn = get_connection()
                try:
                    df_p = pd.read_sql("SELECT * FROM products", conn)
                    if not df_p.empty:
                        st.write("### 📋 현재 시스템에 등록된 단가표 (상위 5개)")
                        preview_df = df_p.head().copy()
                        price_cols = [c for c in preview_df.columns if c not in ['코드', '상품명', '규격', '단위']]
                        format_dict = {}
                        for c in price_cols:
                            preview_df[c] = pd.to_numeric(preview_df[c], errors='coerce').fillna(0).astype(int)
                            format_dict[c] = '{:,}원'
                        st.dataframe(preview_df.style.format(format_dict), use_container_width=True)
                except:
                    pass
                finally:
                    conn.close()

            with t2:
                st.info("💡 팁: 'client_list.xlsx' 파일명으로 깃허브에 올려두시면 매번 업로드할 필요 없이 항상 자동 유지됩니다.")
                f2 = st.file_uploader("천년경영 '거래처목록' 엑셀 수동 업로드", type=["xlsx"], key="admin_c_up")
                if f2 and st.button("거래처 반영"):
                    df_c = process_client_excel(f2)
                    conn = get_connection()
                    df_c.to_sql('clients', conn, if_exists='replace', index=False)
                    conn.close()
                    st.success("✅ 거래처 정보 등록 완료! (초기비번 1234)")
                
                # 상시 미리보기 연동
                conn = get_connection()
                try:
                    df_c = pd.read_sql("SELECT * FROM clients", conn)
                    if not df_c.empty:
                        st.write("### 📋 현재 시스템에 등록된 거래처 정보 (상위 5개)")
                        st.dataframe(df_c.head(), use_container_width=True)
                except:
                    pass
                finally:
                    conn.close()

            with t3:
                st.subheader("🛒 실시간 접수된 주문 목록")
                conn = get_connection()
                try:
                    orders_df = pd.read_sql("SELECT * FROM orders ORDER BY id DESC", conn)
                    if not orders_df.empty:
                        orders_df['price'] = pd.to_numeric(orders_df['price'], errors='coerce').fillna(0).astype(int)
                        orders_df['qty'] = pd.to_numeric(orders_df['qty'], errors='coerce').fillna(0).astype(int)
                        orders_df['total'] = pd.to_numeric(orders_df['total'], errors='coerce').fillna(0).astype(int)
                        
                        display_df = orders_df.rename(columns={
                            'id': '주문번호', 'order_date': '주문일시', 'client_name': '거래처명',
                            'item_name': '품목명', 'spec': '규격', 'unit': '단위',
                            'price': '단가', 'qty': '수량', 'total': '총금액', 'status': '상태'
                        })
                        
                        st.dataframe(display_df.style.format({
                            '단가': '{:,}원', '수량': '{:,}', '총금액': '{:,}원'
                        }), use_container_width=True)
                        
                        if st.button("전체 주문 내역 초기화"):
                            conn.execute("DELETE FROM orders")
                            conn.commit()
                            st.rerun()
                    else:
                        st.info("현재 접수된 새로운 주문이 없습니다.")
                except Exception as e:
                    st.error(f"주문 데이터를 불러오는 중 오류가 발생했습니다: {e}")
                finally:
                    conn.close()

    # --- 거래처 모드 ---
    else:
        st.header("🏗️ 거래처 전용 온라인 발주")
        
        if not st.session_state.is_logged_in:
            with st.form("unique_login_form"):
                c_id = st.text_input("아이디(거래처코드)").strip()
                c_pw = st.text_input("비밀번호", type="password").strip()
                if st.form_submit_button("로그인"):
                    conn = get_connection()
                    user = pd.read_sql(f"SELECT * FROM clients WHERE client_id='{c_id}' AND password='{c_pw}'", conn)
                    conn.close()
                    
                    if not user.empty:
                        st.session_state.is_logged_in = True
                        st.session_state.user_info = {
                            "id": user.iloc[0]['client_id'], 
                            "name": user.iloc[0]['client_name'], 
                            "tier": user.iloc[0]['target_tier']
                        }
                        st.rerun()
                    else:
                        st.error("입력하신 정보가 올바르지 않습니다.")
        else:
            u = st.session_state.user_info
            st.sidebar.success(f"접속: {u['name']}")
            st.sidebar.info(f"적용 단가: {u['tier']}")
            if st.sidebar.button("안전하게 로그아웃"):
                st.session_state.is_logged_in = False
                st.session_state.user_info = None
                st.rerun()

            st.subheader(f"🔍 자재 단가 조회")
            conn = get_connection()
            try:
                data = pd.read_sql(f"SELECT 상품명, 규격, 단위, [{u['tier']}] AS 단가 FROM products", conn)
                search = st.text_input("상품명을 입력하세요 (예: 합판, 시멘트)")
                if search:
                    data = data[data['상품명'].str.contains(search, na=False)]
                
                data['단가'] = pd.to_numeric(data['단가'], errors='coerce').fillna(0).astype(int)
                st.dataframe(data.style.format({'단가': '{:,}원'}), use_container_width=True)
                
                st.divider()
                st.subheader("🛒 실시간 발주")
                col1, col2 = st.columns([3, 1])
                with col1:
                    item_choice = st.selectbox("품목 선택", data['상품명'].tolist())
                with col2:
                    qty_choice = st.number_input("수량", min_value=1, value=1, step=1)
                
                if st.button("🚀 발주서 전송하기"):
                    item_info = data[data['상품명'] == item_choice].iloc[0]
                    
                    kst = datetime.timezone(datetime.timedelta(hours=9))
                    now = datetime.datetime.now(kst).strftime('%Y-%m-%d %H:%M')
                    total_price = int(item_info['단가'] * qty_choice)
                    
                    conn.execute("""INSERT INTO orders (order_date, client_name, item_name, spec, unit, price, qty, total) 
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                                 (now, u['name'], item_choice, item_info['규격'], item_info['단위'], int(item_info['단가']), qty_choice, total_price))
                    conn.commit()
                    
                    alert_msg = (
                        f"🔔 [신규 주문 알림]\n"
                        f"- 업체명: {u['name']}\n"
                        f"- 품목: {item_choice}\n"
                        f"- 규격: {item_info['규격']}\n"
                        f"- 수량: {qty_choice} {item_info['단위']}\n"
                        f"- 총액: {total_price:,}원\n"
                        f"- 일시: {now}"
                    )
                    send_telegram_msg(alert_msg)
                    
                    st.success(f"✅ {item_choice} {qty_choice}개 (총 {total_price:,}원) 주문이 정상 접수되었습니다. (알림 전송 완료)")
                    
            except Exception as e:
                st.warning("단가표 정보를 불러올 수 없습니다. 관리자 모드에서 파일을 먼저 업로드해주세요.")
            finally:
                conn.close()

if __name__ == "__main__":
    main()
