from flask import Flask
app = Flask(__name__)

@app.route("/")
def home ():
    return """ <h1>Welcome to Bookverse Home Page</h1>
               <p>This is a Bookverse flask website.</p>
               <a href='/books'>Books</a> <br> <br>
               <a href='/borrowed'>Borrowed</a> <br> <br>
               <a href='/reviews'>Reviews</a> <br> <br>
               <a href='/about'>About Us</a> <br> <br>
               <a href='/login'>Login</a> <br> <br>
               <a href='/register'>Register</a>    
               """

@app.route("/books")
def books():
    return """<h1>Books Page</h1>
             <p>Browse all available books here.</p>
             <a href='/'>Home</a> <br> <br>
             <a href='/borrowed'>Borrowed</a> <br> <br>
             <a href='/reviews'>Reviews</a> <br> <br>
             <a href='/about'>About Us</a> <br> <br>
             <a href='/login'>Login</a> <br> <br>
             <a href='/register'>Register</a>    
           """            

@app.route("/borrowed")
def borrowed():
    return """<h1>Borrowed Books</h1>
              <p>View all your borrowed books here.</p>
              <a href='/'>Home</a> <br> <br>
              <a href='/books'>Books</a> <br> <br>
              <a href='/reviews'>Reviews</a> <br> <br>
              <a href='/about'>About Us</a> <br> <br>
              <a href='/login'>Login</a> <br> <br>
              <a href='/register'>Register</a>                      
            """
            
@app.route("/reviews")
def reviews():
    return """<h1>Reviews</h1>
              <p>Read and Write book reviews.</p>
              <a href='/'>Home</a> <br> <br>
              <a href='/books'>Books</a> <br> <br>
              <a href='/borrowed'>Borrowed</a> <br> <br>
              <a href='/about'>About Us</a> <br> <br>
              <a href='/login'>Login</a> <br> <br>
              <a href='/register'>Register</a>    
           """  
    
@app.route("/about")
def about():
    return """<h1>About Us</h1>
              <p>Learn more about us.</p>
              <a href='/'>Home</a> <br> <br>
              <a href='/books'>Books</a> <br> <br>
              <a href='/borrowed'>Borrowed</a> <br> <br>
              <a href='/reviews'>Reviews</a> <br> <br>
              <a href='/login'>Login</a> <br> <br>
              <a href='/register'>Register</a>             
           """

@app.route("/login")
def login():
    return """<h1>Login</h1>
              <p>Login to your account.</p>
              <a href='/'>Home</a> <br> <br>
              <a href='/books'>Books</a> <br> <br>
              <a href='/borrowed'>Borrowed</a> <br> <br>
              <a href='/reviews'>Reviews</a> <br> <br>
              <a href='/login'>Login</a> <br> <br>
              <a href='/register'>Register</a>       
           """

@app.route("/register")
def register():
    return """<h1>Register</h1>
              <p>Register if you don't have an account.</p>
              <a href='/'>Home</a> <br> <br>
              <a href='/books'>Books</a> <br> <br>
              <a href='/borrowed'>Borrowed</a> <br> <br>
              <a href='/reviews'>Reviews</a> <br> <br>
              <a href='/login'>Login</a> <br> <br>
              <a href='/register'>Register</a>       
           """

if __name__=="__main__":
    app.run(debug=True)

