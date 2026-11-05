import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def inspect():
    client = AsyncIOMotorClient("mongodb://127.0.0.1:27017")
    dbs = await client.list_database_names()
    print("=== LOCAL MONGODB (127.0.0.1:27017) ===")
    print("Databases found:", dbs)
    for db_name in dbs:
        if db_name in ["admin", "config", "local"]:
            continue
        db = client[db_name]
        cols = await db.list_collection_names()
        print(f"\nDatabase: {db_name}")
        for col_name in sorted(cols):
            count = await db[col_name].count_documents({})
            print(f"  - {col_name}: {count} documents")
    client.close()

if __name__ == "__main__":
    asyncio.run(inspect())
