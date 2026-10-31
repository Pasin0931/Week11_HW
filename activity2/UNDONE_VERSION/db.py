import os
import mysql.connector
from pymongo import MongoClient
import redis

def get_mysql_connection():
    # TODO: Activity 1 - Setup MySQL Connection
    # 1. Use mysql.connector.connect()
    # 2. Get connection details from environment variables (os.getenv)
    # 3. Use host='localhost', user='root', password='rootpassword', database='user_db', port=3306
    try:
        # connection = mysql.connector.connect(...)
        # return connection
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', 'rootpassword'),
            database=os.getenv('DB_NAME', 'user_db'),
            port=int(os.getenv('DB_PORT', '3306'))
        )
        return connection
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL: {err}")
        return None

def get_mongo_collection():
    # TODO: Activity 2 - Setup MongoDB Connection
    # 1. Use MongoClient() with a URI string
    # 2. URI Format: mongodb://localhost:27017/product_db
    # 3. Return the 'products' collection from the database
    try:
        # uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/product_db')
        # client = MongoClient(uri)
        # return client.get_database()['products']
        uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/product_db')
        client = MongoClient(uri)
        return client.get_database()['products']
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

def get_redis_client():
    # TODO: Activity 3 - Setup Redis Client
    # 1. Use redis.Redis()
    # 2. host='localhost', port=6379, decode_responses=True
    try:
        # return redis.Redis(...)
        return redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', '6379')),
            decode_responses=True
        )
    except Exception as e:
        print(f"Error connecting to Redis: {e}")
        return None
