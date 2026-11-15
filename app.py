
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)

# SECURITY CONFIGURATION
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
if not app.config["SECRET_KEY"]:
    raise RuntimeError("Please set the SECRET_KEY environment variable.")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///blog.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


# DATABASE MODELS

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    author = db.relationship("User", backref="posts")


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    author = db.relationship("User")


# USER SESSION

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# HOME PAGE AND TITLE SEARCH

@app.route("/")
def index():
    query = request.args.get("q", "").strip()

    if query:
        posts = Post.query.filter(
            Post.title.ilike(f"%{query}%")
        ).order_by(Post.date.desc()).all()
    else:
        posts = Post.query.order_by(Post.date.desc()).all()

    return render_template(
        "index.html",
        posts=posts,
        query=query
    )


# REGISTRATION

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not username or not email or not password:
            flash("Please fill in every field.")

        elif User.query.filter_by(username=username).first():
            flash("Username already exists.")

        elif User.query.filter_by(email=email).first():
            flash("Email already registered.")

        else:
            user = User(
                username=username,
                email=email,
                password=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()

            flash("Account created successfully! Please log in.")
            return redirect(url_for("login"))

    return render_template("register.html")


# LOGIN

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(
            email=request.form["email"].strip().lower()
        ).first()

        if user and check_password_hash(
            user.password, request.form["password"]
        ):
            login_user(user)
            flash("Login successful!")
            return redirect(url_for("index"))

        flash("Invalid email or password.")

    return render_template("login.html")


# LOGOUT

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have logged out.")
    return redirect(url_for("index"))


# CREATE POST

@app.route("/create", methods=["GET", "POST"])
@login_required
def create_post():
    if request.method == "POST":
        title = request.form["title"].strip()
        content = request.form["content"].strip()

        if title and content:
            post = Post(
                title=title,
                content=content,
                user_id=current_user.id
            )
            db.session.add(post)
            db.session.commit()

            flash("Blog published successfully!")
            return redirect(url_for("index"))

        flash("Title and content are required.")

    return render_template("create_post.html", post=None)


# VIEW POST AND COMMENTS

@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def view_post(post_id):
    post = db.get_or_404(Post, post_id)

    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("Please log in to comment.")
            return redirect(url_for("login"))

        content = request.form["content"].strip()

        if content:
            comment = Comment(
                content=content,
                post_id=post.id,
                user_id=current_user.id
            )
            db.session.add(comment)
            db.session.commit()

            flash("Comment added successfully!")
            return redirect(url_for("view_post", post_id=post.id))

    comments = Comment.query.filter_by(
        post_id=post.id
    ).all()

    return render_template(
        "post.html",
        post=post,
        comments=comments
    )


# EDIT POST

@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
@login_required
def edit_post(post_id):
    post = db.get_or_404(Post, post_id)

    if post.user_id != current_user.id:
        flash("You cannot edit this post.")
        return redirect(url_for("index"))

    if request.method == "POST":
        title = request.form["title"].strip()
        content = request.form["content"].strip()

        if title and content:
            post.title = title
            post.content = content
            db.session.commit()

            flash("Post updated successfully!")
            return redirect(url_for("view_post", post_id=post.id))

        flash("Both fields are required.")

    return render_template("create_post.html", post=post)


# DELETE POST

@app.route("/delete/<int:post_id>", methods=["POST"])
@login_required
def delete_post(post_id):
    post = db.get_or_404(Post, post_id)

    if post.user_id != current_user.id:
        flash("You cannot delete this post.")
        return redirect(url_for("index"))

    Comment.query.filter_by(post_id=post.id).delete()
    db.session.delete(post)
    db.session.commit()

    flash("Post deleted successfully!")
    return redirect(url_for("index"))


# CREATE DATABASE

with app.app_context():
    db.create_all()


# RUN APPLICATION

if __name__ == "__main__":
    app.run(debug=True)
