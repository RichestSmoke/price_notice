from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
import asyncio
import os




load_dotenv(find_dotenv())


async def update_data_on_db(new_orders_list: list) -> str:
    cluster = AsyncIOMotorClient(os.getenv('MONGODB'))
    collection = cluster.Notice_orders.Orders
    not_loaded_orders = ""

    for new_order in new_orders_list:
        update_data = {
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'price': new_order['price'],
            'action': new_order['action']
        }

        coin_query = {'coin': new_order['coin']}
        is_coin_in_db = await collection.find_one(coin_query)

        if is_coin_in_db:
            update_result = await collection.update_one(
                {'_id': is_coin_in_db['_id']},
                {'$push': {'data': update_data}}
            )
            result = True if update_result.modified_count > 0 else False
            if not result:
                not_loaded_orders += f"{new_order['coin'][:-4]}-{new_order['price']}-{new_order['action']}\n"
            
        else:
            data = {
                'coin': new_order['coin'],
                'data': [update_data]
            }
            insert_result = await collection.insert_one(data)
            result = True if insert_result else False
            if not result:
                not_loaded_orders += f"{new_order['coin'][:-4]}-{new_order['price']}-{new_order['action']}\n"

    if not not_loaded_orders:
        not_loaded_orders = "Все ордера загружены успешно!"
    cluster.close()
    return not_loaded_orders


async def show_data_in_db() -> list:
    cluster = AsyncIOMotorClient(os.getenv('MONGODB'))
    collection = cluster.Notice_orders.Orders
    cursor = collection.find({})
    data = []
    async for document in cursor:
        for order in document['data']:
            data.append({
                'coin' : document['coin'],
                'price' : order['price'],
                'action' : order['action']
            })
    cluster.close()
    return data


async def remove_object_from_coin(coin: str, price: int, action: str) -> bool:
    cluster = AsyncIOMotorClient(os.getenv('MONGODB'))
    collection = cluster.Notice_orders.Orders
    
    update_result = await collection.update_one(
        {'coin': f"{coin}"},
        {'$pull': {'data': {'price': price, 'action': action}}}
    )
    result = True if update_result.acknowledged and update_result.modified_count > 0 else False
    print(result)
    cluster.close()
    return result


async def remove_data_for_coin(coin) -> bool:
    cluster = AsyncIOMotorClient(os.getenv('MONGODB'))
    collection = cluster.Notice_orders.Orders
    update_result = await collection.delete_one({'coin': coin})
    result = True if update_result.acknowledged and update_result.deleted_count > 0 else False
    cluster.close()
    return result


async def clear_entire_collection() -> bool:
    cluster = AsyncIOMotorClient(os.getenv('MONGODB'))
    collection = cluster.Notice_orders.Orders
    update_result = await collection.delete_many({})
    result = True if update_result.acknowledged and update_result.deleted_count > 0 else False
    cluster.close()
    return result



if __name__ == "__main__":
    asyncio.run(update_data_on_db())

    