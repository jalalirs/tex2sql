
import asyncio
import asyncpg

async def test():
    try:
        conn = await asyncpg.connect('postgresql://postgres:password123@localhost:5432/tex2sql')
        result = await conn.fetchval('SELECT 1')
        await conn.close()
        print('✅ Database connection successful!')
        return True
    except Exception as e:
        print(f'❌ Database connection failed: {e}')
        return False

asyncio.run(test())
