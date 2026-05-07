import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def get_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing in .env")
    return create_client(url, key)

def load_es_15min(start_date=None, end_date=None, session_only=True):
    supabase = get_supabase_client()
    
    count_res = supabase.table('es_15min').select('*', count='exact').limit(0).execute()
    total = count_res.count
    print(f"Total rows available: {total}")
    
    all_data = []
    offset = 0
    batch = 1000
    while True:
        query = supabase.table('es_15min').select('*').order('timestamp').range(offset, offset + batch - 1)
        if start_date:
            query = query.gte('timestamp', start_date)
        if end_date:
            query = query.lte('timestamp', end_date)
        response = query.execute()
        if not response.data:
            break
        all_data.extend(response.data)
        offset += batch
        if len(response.data) < batch:
            break
    
    df = pd.DataFrame(all_data)
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    if session_only:
        df = df[(df['timestamp'].dt.hour >= 9) & (df['timestamp'].dt.hour < 16)]
        df = df[~((df['timestamp'].dt.hour == 9) & (df['timestamp'].dt.minute < 30))]
        df = df[~((df['timestamp'].dt.hour == 16) & (df['timestamp'].dt.minute > 0))]
    
    return df