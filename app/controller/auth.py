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
    
    def dashboard(self):
        stats = [
            {
                'label': 'Total books',
                'value': '8,420',
                'delta': '+12%',
                'description': 'Catalog volume across all active shelves.'
            },
            {
                'label': 'Active members',
                'value': '1,201',
                'delta': '+5.4%',
                'description': 'Members with active library accounts.'
            },
            {
                'label': 'Issued today',
                'value': '128',
                'delta': '-1.2%',
                'description': 'Books checked out in the last 24 hours.'
            },
            {
                'label': 'Overdue',
                'value': '23',
                'delta': '-8%',
                'description': 'Loans past their due date needing follow-up.'
            }
        ]

        recent_books = [
            {
                'title': 'The Midnight Library',
                'author': 'Matt Haig',
                'category': 'Fiction',
                'status': 'Available',
                'status_class': 'available'
            },
            {
                'title': 'Atomic Habits',
                'author': 'James Clear',
                'category': 'Self-help',
                'status': 'Issued',
                'status_class': 'issued'
            },
            {
                'title': 'Educated',
                'author': 'Tara Westover',
                'category': 'Memoir',
                'status': 'Reserved',
                'status_class': 'reserved'
            },
            {
                'title': 'Deep Work',
                'author': 'Cal Newport',
                'category': 'Productivity',
                'status': 'Available',
                'status_class': 'available'
            }
        ]

        issued_books = [
            {
                'member': 'Priya Patel',
                'title': 'Atomic Habits',
                'author': 'James Clear',
                'category': 'Self-help',
                'due_date': 'Jun 02',
                'status': 'Due soon'
            },
            {
                'member': 'Rahul Sharma',
                'title': 'Rich Dad Poor Dad',
                'author': 'Robert Kiyosaki',
                'category': 'Business',
                'due_date': 'May 30',
                'status': 'Overdue'
            },
            {
                'member': 'Ananya Singh',
                'title': 'The Alchemist',
                'author': 'Paulo Coelho',
                'category': 'Fiction',
                'due_date': 'Jun 05',
                'status': 'On loan'
            }
        ]

        return render_template('dashboard.html', stats=stats, recent_books=recent_books, issued_books=issued_books)
    
    def borrowed(self):
        return render_template('borrowedpage.html')
    
    def login_enhanced(self):
        return render_template('index_enhanced.html')
    
