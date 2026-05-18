from flask import render_template

class AuthController:
    def login(self):
        return render_template('login.html')

    def register(self):
        return render_template('register.html')

    def home(self):
        return render_template('home.html')

    def about(self):
        return render_template('about.html')

    def books(self):
        return render_template('books.html')

    def contact(self):
        return render_template('contact.html')

    def profile(self):
        return render_template('profile.html')

    def services(self):
        return render_template('services.html')