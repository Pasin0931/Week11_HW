from flask import Flask, jsonify, request, render_template
from db import get_mysql_connection, get_mongo_collection, get_redis_client
import mysql.connector

app = Flask(__name__)

# --- Frontend Route ---
@app.route('/')
def index():
    return render_template('index.html')

# --- Health Check ---
@app.route('/health', methods=['GET'])
def health_check():
    status = {
        'mysql': 'down',
        'mongo': 'down',
        'redis': 'down'
    }

    # Check MySQL
    try:
        conn = get_mysql_connection()
        if conn and conn.is_connected():
            status['mysql'] = 'up'
            conn.close()
    except Exception:
        pass

    # Check MongoDB
    try:
        products_col = get_mongo_collection()
        if products_col is not None:
            # Simple command to check connection
            products_col.database.command('ping')
            status['mongo'] = 'up'
    except Exception:
        pass

    # Check Redis
    try:
        r = get_redis_client()
        if r.ping():
            status['redis'] = 'up'
    except Exception:
        pass

    return jsonify(status)


import json
import time

# --- Product API (MongoDB + Redis) ---
@app.route('/products', methods=['POST'])
def create_product():
    data = request.json
    if not data.get('_id') or not data.get('name'):
        return jsonify({"error": "Product _id and name are required"}), 400

    products_col = get_mongo_collection()
    if products_col is None:
        return jsonify({"error": "MongoDB connection failed"}), 500

    try:
        products_col.insert_one(data)
        
        # --- TODO: Activity 5 - Implement Cache Invalidation ---
        # When a new product is added, the 'product_list' cache is now STALE.
        # 1. Get redis client
        # 2. Delete 'product_list' key from Redis
        # print(">>> [REDIS] Cache Invalidated: product_list deleted due to new product")
        r = get_redis_client()
        if r:
            r.delete('product_list')
            print(">>> [REDIS] Cache Invalidated: product_list deleted due to new product")
            
        return jsonify({"message": "Product created", "id": data['_id']}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/products', methods=['GET'])
def list_products():
    # --- TODO: Activity 4 - Implement Lazy Loading Pattern (List) ---
    # CONCEPT: WHAT IS LAZY LOADING? (Cache-Aside Pattern)
    # Lazy loading means we only load data into the cache when it is requested.
    # 
    # THE STEPS:
    # 1. CHECK CACHE: Look for 'product_list' in Redis.
    # 2. CACHE HIT: If found, return it immediately. (Fastest)
    # 3. CACHE MISS: If not found, fetch from the "Source of Truth" (MongoDB).
    # 4. POPULATE CACHE: Save the fetched data back to Redis so next time it's a "Hit".
    
    r = get_redis_client()
    # Your code here...
    redis_key = 'product_list'
    if r:
        cached = r.get(redis_key)
        if cached:
            print(f">>> [REDIS] Cache Hit: {redis_key}")
            return jsonify(json.loads(cached))
        print(f">>> [REDIS] Cache Miss: {redis_key}")

    # Fallback to source of truth (MongoDB)
    print(">>> [MONGO] Fetching from MongoDB...")
    products_col = get_mongo_collection()
    if products_col is None:
        return jsonify({"error": "MongoDB connection failed"}), 500

    products = list(products_col.find())
    if r:
        r.setex(redis_key, 60, json.dumps(products, default=str))
        print(f">>> [REDIS] Cache Populated: {redis_key}")
    return jsonify(json.loads(json.dumps(products, default=str)))

@app.route('/products/<product_id>', methods=['GET'])
def get_product(product_id):
    # --- TODO: Activity 6 - Implement Lazy Loading for Individual Product ---
    # Concept: Same as Activity 4, but for a specific ID instead of a list.
    # Hint: Use redis key format "product:{product_id}"
    
    redis_key = f"product:{product_id}"
    r = get_redis_client()
    # Your code here...
    if r:
        cached = r.get(redis_key)
        if cached:
            print(f">>> [REDIS] Cache Hit: {redis_key}")
            return jsonify(json.loads(cached))
        print(f">>> [REDIS] Cache Miss: {redis_key}")

    products_col = get_mongo_collection()
    if products_col is None:
        return jsonify({"error": "MongoDB connection failed"}), 500

    product = products_col.find_one({"_id": product_id})
    if not product:
        return jsonify({"error": "Product not found"}), 404

    if r:
        r.setex(redis_key, 60, json.dumps(product, default=str))
        print(f">>> [REDIS] Cache Populated: {redis_key}")
    return jsonify(json.loads(json.dumps(product, default=str)))

# --- Cache Management ---
@app.route('/cache/remove', methods=['POST'])
def remove_cache():
    # --- TODO: Activity 7 - Implement Bulk Cache Invalidation (The "Nuke" Button) ---
    # Students should learn how to clear specific keys or scan for patterns.
    # Hint: Use r.delete('user_list') and r.scan_iter("user:*")
    
    r = get_redis_client()
    if not r:
        return jsonify({"error": "Redis connection failed"}), 500

    try:
        # Your code here to remove product_list, product:*, user_list, and user:*
        r.delete('product_list', 'user_list')
        for key in r.scan_iter("product:*"):
            r.delete(key)
        for key in r.scan_iter("user:*"):
            r.delete(key)
        print(">>> [REDIS] Cache Removed: product_list, product:*, user_list, user:*")
        return jsonify({"message": "All product and user cache entries were removed."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/cache/all', methods=['GET'])
def get_all_cache():
    r = get_redis_client()
    if not r:
        return jsonify({"error": "Redis connection failed"}), 500
    
    try:
        keys = r.keys("*")
        cache_data = {}
        for key in keys:
            # Skip internal metadata keys that students don't need to see
            if key == 'cache_last_refresh':
                continue
                
            val = r.get(key)
            try:
                # Try to parse JSON for better display
                cache_data[key] = json.loads(val)
            except:
                cache_data[key] = val
        return jsonify(cache_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/cache/status', methods=['GET'])
def cache_status():
    r = get_redis_client()
    if not r:
        return jsonify({"error": "Redis connection failed"}), 500

    # TODO: Activity 8 - Return the count of cached keys
    # Hint: Use r.dbsize() or fetch all keys and count them.
    total_keys = r.dbsize()
    
    return jsonify({
        "total_cached_keys": total_keys
    })

# --- Database Initialization ---
def init_mysql_db():
    conn = get_mysql_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                role ENUM('admin', 'user') NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("MySQL 'users' table initialized.")

# --- User API (MySQL) ---
@app.route('/users', methods=['POST'])
def create_user():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    role = data.get('role', 'user')

    if not username or not email:
        return jsonify({"error": "Username and email are required"}), 400

    conn = get_mysql_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, role) VALUES (%s, %s, %s)",
            (username, email, role)
        )
        conn.commit()
        user_id = cursor.lastrowid
        cursor.close()
        conn.close()

        # --- TODO: Activity 5 (Again) - Implement Cache Invalidation ---
        # Don't forget to invalidate 'user_list'!
        r = get_redis_client()
        if r:
            r.delete('user_list')
            print(">>> [REDIS] Cache Invalidated: user_list deleted due to new user")

        return jsonify({"id": user_id, "message": "User created"}), 201
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    # --- TODO: Activity 6 (Again) ---
    redis_key = f"user:{user_id}"
    r = get_redis_client()
    if r:
        cached = r.get(redis_key)
        if cached:
            print(f">>> [REDIS] Cache Hit: {redis_key}")
            return jsonify(json.loads(cached))
        print(f">>> [REDIS] Cache Miss: {redis_key}")
    
    conn = get_mysql_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        if r:
            r.setex(redis_key, 60, json.dumps(user, default=str))
            print(f">>> [REDIS] Cache Populated: {redis_key}")
        return jsonify(json.loads(json.dumps(user, default=str)))
    else:
        return jsonify({"error": "User not found"}), 404

@app.route('/users', methods=['GET'])
def list_users():
    # --- TODO: Activity 4 (Again) - Lazy Loading for Users ---
    # Remember the pattern: Check Redis -> If Miss, Query MySQL -> Save to Redis.
    redis_key = 'user_list'
    r = get_redis_client()
    if r:
        cached = r.get(redis_key)
        if cached:
            print(f">>> [REDIS] Cache Hit: {redis_key}")
            return jsonify(json.loads(cached))
        print(f">>> [REDIS] Cache Miss: {redis_key}")
    
    conn = get_mysql_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()

    if r:
        r.setex(redis_key, 60, json.dumps(users, default=str))
        print(f">>> [REDIS] Cache Populated: {redis_key}")
    return jsonify(json.loads(json.dumps(users, default=str)))

if __name__ == '__main__':
    # Initialize DB on start (in production, use migration tools)
    # We delay this slightly or handle errors if DB isn't ready immediately in docker
    # For this activity, we'll assume it's ready or user will retry
    try:
        init_mysql_db()
    except Exception as e:
        print(f"Warning: DB init failed: {e}")

    app.run(host='0.0.0.0', port=5001, debug=True)
