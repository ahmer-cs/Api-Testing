# import os
# import os
# import psycopg2
# from dotenv import load_dotenv
# from flask import Flask,request,jsonify


# CREATE_USERS_TABLE = (
#     """CREATE TABLE IF NOT EXISTS users (
#     user_id SERIAL PRIMARY KEY,
#     email VARCHAR(255) NOT NULL,
#     password VARCHAR(255) NOT NULL);"""
# )
# CREATE_BLOGPOST_TABLE = """CREATE TABLE IF NOT EXISTS blog_posts (
#     post_id SERIAL PRIMARY KEY,
#     title VARCHAR(255) NOT NULL,
#     content TEXT,
#     user_id INT NOT NULL,
#     FOREIGN KEY (user_id) REFERENCES users(user_id)
# );"""

# CREATE_COMMENT_TABLE = """CREATE TABLE comments (
#     comment_id SERIAL PRIMARY KEY,
#     content TEXT NOT NULL,
#     user_id INT NOT NULL,
#     post_id INT NOT NULL,
#     FOREIGN KEY (user_id) REFERENCES users(user_id),
#     FOREIGN KEY (post_id) REFERENCES blog_posts(post_id)
# );"""


# # Example: Insert a user into the 'users' table
# insert_user_sql = """INSERT INTO users (email, password) VALUES (%s, %s);"""


# # Example: Insert a blog post into the 'blog_posts' table
# insert_blog_post_sql = """INSERT INTO blog_posts (title, content, user_id) VALUES (%s, %s, %s);"""


# insert_comment_sql = """INSERT INTO comments (content, user_id, post_id) VALUES (%s, %s, %s);"""


# load_dotenv()  # loads variables from .env file into environment

# app = Flask(__name__)
# url = os.environ.get("DATABASE_URL")  # gets variables from environment
# connection = psycopg2.connect(url)

# # @app.post("/api/user")
# @app.route('/api/user',methods=['GET','POST'])
# def create_user():
#     data = request.get_json()
#     email = data["email"]
#     password = data["password"]
#     with connection:
#         with connection.cursor() as cursor:
#             cursor.execute(CREATE_USERS_TABLE)
#             cursor.execute(insert_user_sql, (email, password))
#     return {"message": f"User {email} created."}, 201

# @app.route('/api/blogpost', methods=['POST'])
# def create_blog_post():
#     data = request.get_json()
#     title = data['title']
#     content = data['content']
#     user_id = data['user_id']  # You may need to authenticate the user and get their ID

#     if not title or not content or user_id is None:
#         return jsonify({"error": "Missing required data"}), 400

#     with connection:
#         with connection.cursor() as cursor:
#             cursor.execute(CREATE_BLOGPOST_TABLE)
#             cursor.execute(insert_blog_post_sql, (title, content, user_id))

#     return jsonify({"message": "Blog post created successfully"}), 201
import os
from psycopg2 import IntegrityError
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import re
# from flask_restplus import Api, Resource, fields
import psycopg2  # For email validation

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.environ.get("JWT_SECRET_KEY")
jwt = JWTManager(app)

# Database connection
url = os.environ.get("DATABASE_URL")
connection = psycopg2.connect(url)

# SQL statements
CREATE_USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL
);
"""

CREATE_BLOGPOST_TABLE = """
    CREATE TABLE IF NOT EXISTS blog_posts (
    post_id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    user_id INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
"""

CREATE_COMMENT_TABLE = """
    CREATE TABLE IF NOT EXISTS comments (
    comment_id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    user_id INT NOT NULL,
    post_id INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (post_id) REFERENCES blog_posts(post_id)
);
"""

insert_user_sql = """INSERT INTO users (email, password) VALUES (%s, %s) RETURNING user_id;"""
insert_blog_post_sql = """INSERT INTO blog_posts (title, content, user_id) VALUES (%s, %s, %s) RETURNING post_id;"""
delete_user_sql = "DELETE FROM users WHERE user_id = %s;"
delete_blog_post_sql = "DELETE FROM blog_posts WHERE post_id = %s;"

# Email validation pattern
email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$"

def is_valid_email(email):
    return re.match(email_pattern, email)

@app.route('/api/user', methods=['POST'])
def create_user():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Missing required data"}), 400

    if not is_valid_email(email):
        return jsonify({"error": "Invalid email address"}), 400

    with connection, connection.cursor() as cursor:
        cursor.execute(CREATE_USERS_TABLE)
    
    # Check if the email or password already exists
        cursor.execute("SELECT email, password FROM users WHERE email = %s OR password = %s;", (email, password))
        existing_user = cursor.fetchone()

        if existing_user:
            existing_email, existing_password = existing_user
            error_message = "Email already in use" if existing_email == email else "Password already in use"
            return jsonify({"error": error_message}), 400
    
    # If no existing user is found, insert the new user
        cursor.execute(insert_user_sql, (email, password))
        user_id = cursor.fetchone()[0]

    access_token = create_access_token(identity=email)
    return jsonify({"user_id": user_id, "access_token": access_token}), 201


@app.route('/api/blogpost', methods=['POST'])
@jwt_required()
def create_blog_post():
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    user_email = get_jwt_identity()  # Get user's email from the JWT

    if not title or not content:
        return jsonify({"error": "Missing required data"}), 400

    with connection, connection.cursor() as cursor:
        cursor.execute(CREATE_BLOGPOST_TABLE)
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (user_email,))
        user_id = cursor.fetchone()[0]
        cursor.execute(insert_blog_post_sql, (title, content, user_id))
        post_id = cursor.fetchone()[0]

    return jsonify({"message": "Blog post created successfully", "post_id": post_id}), 201


@app.route('/api/user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    with connection, connection.cursor() as cursor:
        # First, delete associated blog posts
        cursor.execute("DELETE FROM blog_posts WHERE user_id = %s;", (user_id,))

        # Then, delete the user
        cursor.execute(delete_user_sql, (user_id,))

    return jsonify({"message": f"User {user_id} and associated user deleted"}), 200

if __name__ == '__main__':
    app.run()
