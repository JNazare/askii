#!flask/bin/python
from flask import Flask, jsonify, abort, make_response, request, url_for, render_template, redirect, session
from flask.ext.httpauth import HTTPBasicAuth
import os
from pymongo import MongoClient
from bson.objectid import ObjectId
import keys
import time
import numpy as np
import random
import re
from functools import wraps
import base64
import hashlib
from collections import OrderedDict

### MONGO CONNECTION ###
def connect():
    mongo_keys = keys.mongoKeys()
    connection = MongoClient(mongo_keys[0],mongo_keys[1])
    handle = connection[mongo_keys[2]]
    handle.authenticate(mongo_keys[3],mongo_keys[4])
    return handle


app = Flask(__name__)
app.secret_key = keys.sessionSecret()
auth = HTTPBasicAuth()
askiiHandle = connect()
numNoRepeat = 3

def connectToCustomDB(request_args):
    # Need to initialize a second DB connection for API creators
    key = request_args.get("key", None)
    customHandle = None
    if key:
        user = askiiHandle.askii_users.find_one({"key": key})
        if user == None:
            abort(404)
        dbconfig = user["dbconfig"]
        connection = MongoClient(dbconfig["subdomain"]+".mongolab.com",int(dbconfig["port"]))
        customHandle = connection[dbconfig["mongoId"]]
        customHandle.authenticate(dbconfig["username"], dbconfig["password"])
        collection_names = customHandle.collection_names()
        if "users" not in collection_names:
            customHandle.create_collection("users")
        if "order" not in collection_names:
            customHandle.create_collection("order")
            writeResponse = customHandle.order.insert({"order": []})
        if "questions" not in collection_names:
            customHandle.create_collection("questions")
    return customHandle

#### HELPER FUNCTIONS ####
def make_public_question(question):
    '''Making public uris for questions'''
    new_question = {}
    for field in question:
        if field == '_id':
            new_question['uri'] = url_for('get_question', question_id=question['_id'], _external=True)
        else:
            new_question[field] = question[field]
        new_question["info_uri"] = url_for('get_info', question_id=question['_id'], _external=True)
    return new_question

def make_public_user(user):
    '''Making public uris for users'''
    new_user = {}
    for field in user:
        if field == '_id':
            new_user['uri'] = url_for('get_user', user_id=user['_id'], _external=True)
        else:
            new_user[field] = user[field]
    return new_user

def calculate_difficulty(num_answer, current_difficulty):
    int_answer = -1
    if num_answer == 0:
        int_answer = 1
    if current_difficulty >= 3 and int_answer > 0:
        pass
    elif current_difficulty <= 0 and int_answer < 1:
        pass
    else:
        current_difficulty = current_difficulty + int_answer
    return current_difficulty

def probabilityOfNewQuestion(prob_new):
    prob_review = 1.0 - prob_new
    weighted_choices = [(True, prob_new), (False, prob_review)]
    choices, weights = zip(*weighted_choices)
    return np.random.choice(choices, p=weights)

def findRecentlyAnswered(possible_review_questions):
    od = list(OrderedDict(sorted(possible_review_questions.items(),key = lambda x :x[1]['time_question_last_seen'],reverse = True)))
    od = od[0:numNoRepeat]
    return od

def leitnerBoxSelection(possible_review_questions):

    recently_answered_questions = set(findRecentlyAnswered(possible_review_questions))

    for recent in recently_answered_questions:
        del possible_review_questions[recent]

    easy_weight = 0.1
    medium_weight = 0.2
    hard_weight = 0.3
    very_hard_weight = 0.4
    
    easy_questions = [q for q,v in possible_review_questions.iteritems() if int(v["difficulty"])==0] # get all questions with 0 difficulty
    medium_questions = [q for q,v in possible_review_questions.iteritems() if int(v["difficulty"])==1]
    hard_questions = [q for q,v in possible_review_questions.iteritems() if int(v["difficulty"])==2]
    very_hard_questions = [q for q,v in possible_review_questions.iteritems() if int(v["difficulty"])==3]


    weighted_choices = [(easy_questions, easy_weight), (medium_questions, medium_weight), 
                        (hard_questions, hard_weight), (very_hard_questions, very_hard_weight)]
    
    choices, weights = zip(*weighted_choices)

    chosen_question_catagory = []
    while len(chosen_question_catagory) == 0:
        chosen_question_catagory = np.random.choice(choices, p=weights)

    return random.choice(chosen_question_catagory)

def generateAPIKey():
    return base64.b64encode(hashlib.sha256( str(random.getrandbits(256)) ).digest(), random.choice(['rA','aZ','gQ','hH','hG','aR','DD'])).rstrip('==')

#### AUTHORIZATION FUNCTIONS ###
@auth.get_password
def get_password(username):
    auth_keys = keys.authKeys()
    if username == auth_keys[0]:
        return auth_keys[1]
    return None

@auth.error_handler
def unauthorized():
    return make_response(jsonify({'error': 'Unauthorized access'}), 401)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user", None) is None:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

#### ROUTES ####

@app.route('/')
@login_required
def index():
    return render_template('index.html', user=session["user"])

@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    username = request.form.get("username", None).lower()
    password = request.form.get("password", None)
    # if [username, password] != keys.authKeys():
    if username not in keys.authUsernames() and password != keys.authPassword():
        return redirect(url_for('login', next=request.url))
    askiiUser = askiiHandle.askii_users.find_one({"username": username})
    if askiiUser == None:
        askiiUser = {"username": username, "key": generateAPIKey(), "dbconfig": {}}
        askiiHandle.askii_users.insert(askiiUser)
    if askiiUser.get("_id", None):
        askiiUser["_id"]=unicode(askiiUser["_id"])
    session["user"]=askiiUser
    return redirect(url_for('index', next=request.url))

@app.route('/setupDB', methods=['POST'])
@login_required
def setup_database():
    config_vars = request.form.to_dict()
    writeResponse = askiiHandle.askii_users.update({"_id": ObjectId(unicode(session["user"]["_id"]))}, {'$set': {"dbconfig": config_vars}})
    if int(writeResponse.get('nModified', 0)) == 0:
        abort(404)
    session["user"]["dbconfig"]=config_vars
    return 'done'

# CONTENT ROUTE
@app.route('/askii/info/<question_id>', methods=['GET'])
#@auth.login_required
def get_info(question_id):
    question = handle.questions.find_one({"_id": ObjectId(unicode(question_id))})
    if question == None:
        abort(404)
    question = make_public_question(question)
    return render_template('info.html', question=question)

# QUESTION ROUTES [DATA ENTRY]
@app.route('/askii/api/v1.0/questions', methods=['GET'])
#@auth.login_required
def get_questions():
    handle = connectToCustomDB(request.args)
    if handle == None:
        abort(404)
    '''Get a list of all questions'''
    return jsonify({'questions': [make_public_question(question) for question in handle.questions.find()]})

@app.route('/askii/api/v1.0/questions/<question_id>', methods=['GET'])
#@auth.login_required
def get_question(question_id):
    '''Get a question by _id'''
    handle = connectToCustomDB(request.args)
    if handle == None:
        abort(404)
    question = handle.questions.find_one({"_id": ObjectId(unicode(question_id))})
    if question == None:
        abort(404)
    return jsonify({'question': make_public_question(question)})

@app.route('/askii/api/v1.0/questions', methods=['POST'])
#@auth.login_required
def create_question():
    handle = connectToCustomDB(request.args)
    if handle == None:
        abort(404)
    '''Create new question and append to end of question list'''
    if not request.json or not 'question' in request.json:
        abort(400)
    order_obj = handle.order.find()[0]
    order_id = order_obj["_id"]
    order_list = order_obj.get("order", [])
    question = {
        'question': request.json['question'],
        'answer': request.json.get('answer', ""),
        'difficulty': request.json.get('difficulty', 0)
    }
    already_input_fields = set(question.keys())
    additional_fields = [q for q in request.json if q not in already_input_fields]
    for field in additional_fields:
        question[field] = request.json.get(field, "")
    question_id = handle.questions.insert(question)
    question["_id"] = question_id
    index = request.json.get('index', None)
    if index == None:
        order_list.append(unicode(question["_id"]))
    else:
        order_list.insert(index, unicode(question["_id"]))
    writeResponse = handle.order.update({"_id": ObjectId(unicode(order_id))}, {'$set': {"order": order_list}})
    if int(writeResponse.get('nModified', 0)) == 0:
        abort(404)
    return jsonify({'question': make_public_question(question)}), 201

@app.route('/askii/api/v1.0/questions/<question_id>', methods=['PUT'])
#@auth.login_required
def update_question(question_id):
    handle = connectToCustomDB(request.args)
    if handle == None:
        abort(404)
    '''Update a question by _id'''
    updated_question_fields = {}
    #question = [question for question in questions if question['_id'] == question_id] # get question from mongodb
    if not request.json:
        abort(400)
    if 'question' in request.json and type(request.json['question']) != unicode:
        abort(400)
    if 'answer' in request.json and type(request.json['answer']) is not unicode:
        abort(400)
    if 'content' in request.json and type(request.json['content']) is not unicode:
        abort(400)
    if 'hint' in request.json and type(request.json['hint']) is not unicode:
        abort(400)
    if 'regex' in request.json and type(request.json['regex']) is not unicode:
        abort(400)
    if request.json.get('question', None) != None:
        updated_question_fields['question'] = request.json['question']
    if request.json.get('answer', None) != None:
        updated_question_fields['answer'] = request.json['answer']
    if request.json.get('content', None) != None:
        updated_question_fields['content'] = request.json['content']
    if request.json.get('hint', None) != None:
        updated_question_fields['hint'] = request.json['hint']
    if request.json.get('regex', None) != None:
        updated_question_fields['regex'] = request.json['regex']
    writeResponse = handle.questions.update({"_id": ObjectId(unicode(question_id))}, {'$set': updated_question_fields})
    if int(writeResponse.get('nModified', 0)) == 0:
        abort(404)
    question = updated_question_fields.copy()
    question.update({"_id": question_id})
    return jsonify({'question': make_public_question(question)})

@app.route('/askii/api/v1.0/questions/<question_id>', methods=['DELETE'])
#@auth.login_required
def delete_question(question_id):
    handle = connectToCustomDB(request.args)
    if handle == None:
        abort(404)
    '''Delete a question by _id'''
    order_obj = handle.order.find()[0]
    order_id = order_obj["_id"]
    order_list = order_obj["order"]
    deleteResponse = handle.questions.remove({"_id": ObjectId(unicode(question_id))})
    if int(deleteResponse.get('n', 0)) == 0:
        abort(404)
    if question_id in order_list:
        order_list.remove(question_id)
        writeResponse = handle.order.update({"_id": ObjectId(unicode(order_id))}, {'$set': {"order": order_list}})
        if int(writeResponse.get('nModified', 0)) == 0:
            abort(404)
    return jsonify({'result': True})

# USER FUNCTIONS
@app.route('/askii/api/v1.0/users', methods=['GET'])
#@auth.login_required
def get_users():
    handle = connectToCustomDB(request.args)
    if handle == None:
        abort(404)
    '''Get a list of all users'''
    # return jsonify({'questions': [make_public_question(question) for question in handle.questions.find()]})
    return jsonify({'users': [make_public_user(user) for user in handle.users.find()]})

@app.route('/askii/api/v1.0/users/<user_id>', methods=['GET'])
#@auth.login_required
def get_user(user_id):
    handle = connectToCustomDB(request.args)
    if handle == None:
        abort(404)
    '''Get a user by _id'''
    user = handle.users.find_one({"_id": ObjectId(unicode(user_id))})
    if user == None:
        return jsonify({'user': False})
    return jsonify({'user': make_public_user(user)})

@app.route('/askii/api/v1.0/users/phone_num/<phone_num>', methods=['GET'])
#@auth.login_required
def get_user_by_phone_num(phone_num):
    handle = connectToCustomDB(request.args)
    if handle == None:
        abort(404)
    '''Get a user by phone_num'''
    user = handle.users.find_one({"phone_num": phone_num})
    if user == None:
        return jsonify({'user': False})
    return jsonify({'user': make_public_user(user)})

@app.route('/askii/api/v1.0/users/username/<username>', methods=['GET'])
#@auth.login_required
def get_user_by_username(username):
    handle = connectToCustomDB(request.args)
    if handle == None:
        abort(404)
    '''Get a user by phone_num'''
    user = handle.users.find_one({"username": username})
    if user == None:
        return jsonify({'user': False})
    return jsonify({'user': make_public_user(user)})

@app.route('/askii/api/v1.0/users', methods=['POST'])
#@auth.login_required
def create_user():
    handle = connectToCustomDB(request.args)
    if handle == None:
        abort(404)
    '''Create new user and append to end of user list'''
    if not request.json:
        abort(400)
    user = {
        'phone_num': request.json.get('phone_num', ""),
        'username': request.json.get('username', ""),
        'password': request.json.get("password", ""),
        'email': request.json.get("email", ""),
        'name': request.json.get('name', ""),
        'questions' : {}
    }
    print user
    handle.users.insert(user)
    return jsonify({'user': make_public_user(user)}), 201

####### changed
@app.route('/askii/api/v1.0/users/<user_id>', methods=['POST'])
#@auth.login_required
def update_user(user_id):
    handle = connectToCustomDB(request.args)
    if handle == None:
        abort(404)
    '''Update a user by _id'''
    updated_user_fields = {}
    if not request.json:
        abort(400)
    if 'phone_num' in request.json and type(request.json['phone_num']) != unicode:
        abort(400)
    if 'name' in request.json and type(request.json['name']) != unicode:
        abort(400)
    if request.json.get('phone_num', None) != None:
        updated_user_fields['phone_num'] = request.json['phone_num']
    if request.json.get('name', None) != None:
        updated_user_fields['name'] = request.json['name']
    writeResponse = handle.users.update({"_id": ObjectId(unicode(user_id))}, {'$set': updated_user_fields})
    if int(writeResponse.get('nModified', 0)) == 0:
        abort(404)
    updated_user_fields.update({"_id": user_id})
    return jsonify({'user': make_public_user(updated_user_fields)})

@app.route('/askii/api/v1.0/users/<user_id>', methods=['DELETE'])
#@auth.login_required
def delete_user(user_id):
    handle = connectToCustomDB(request.args)
    if handle == None:
        abort(404)
    '''Delete a user by _id'''
    deleteResponse = handle.users.remove({"_id": ObjectId(unicode(user_id))})
    if int(deleteResponse.get('n', 0)) == 0:
        abort(404)
    return jsonify({'result': True})


### ANSWER QUESTION ###
####### changed
@app.route('/askii/api/v1.0/users/<user_id>/<question_id>', methods=['POST'])
#@auth.login_required
def answer_question(user_id, question_id):
    handle = connectToCustomDB(request.args)
    if handle == None:
        abort(404)
    '''Takes in user_id, question_id, and answer in '1' and '0' for right and wrong'''
    user = handle.users.find_one({"_id": ObjectId(unicode(user_id))})
    question = handle.questions.find_one({"_id": ObjectId(unicode(question_id))})
    user_questions = user["questions"]
    already_answered_question = user_questions.get(question_id, None)
    updated_question = {}
    if not request.json:
        abort(400)
    if 'answer' in request.json and type(request.json['answer']) != unicode:
        abort(400)
    if request.json.get('answer', None) != None:
        answer = int(request.json['answer'])
        if already_answered_question == None:
            updated_question["difficulty"] = calculate_difficulty(answer, int(question.get("difficulty", 0)))
            updated_question["total_times_answered"] = 1
            if answer == 1:
                updated_question["total_times_answered_correctly"] = 1
            else:
                updated_question["total_times_answered_correctly"] = 0
        else:
            updated_question["difficulty"] = calculate_difficulty(answer, int(already_answered_question["difficulty"]))
            updated_question["total_times_answered"] = int(already_answered_question["total_times_answered"])+1
            if answer == 1:
                updated_question["total_times_answered_correctly"] = int(already_answered_question["total_times_answered_correctly"])+1
            else:
                updated_question["total_times_answered_correctly"] = int(already_answered_question["total_times_answered_correctly"])
        updated_question["time_question_last_seen"] = time.time()
        user_questions[question_id]=updated_question
        writeResponse = handle.users.update({"_id": ObjectId(unicode(user_id))}, {'$set': {"questions": user_questions}})
        if int(writeResponse.get('nModified', 0)) == 0:
            abort(404)
        user.update({"questions": user_questions})
    else:
        abort(404)
    return jsonify({"updated_question": updated_question})

### GET NEXT QUESTION ###
@app.route('/askii/api/v1.0/next/<user_id>', methods=['POST'])
#@auth.login_required
def get_next_question(user_id):
    handle = connectToCustomDB(request.args)
    if handle == None:
        abort(404)
    '''Takes in a user_id and a count(total number of questions answered this session)'''
    order_obj = handle.order.find()[0]
    order_id = order_obj["_id"]
    order_list = order_obj["order"]
    user = handle.users.find_one({"_id": ObjectId(unicode(user_id))})
    user_questions = user["questions"]
    already_answered_questions = set(user_questions.keys())
    unanswered_questions = [q for q in order_list if q not in already_answered_questions]
    # need to get the set of questions that are in order but not in the review dictionary
    if int(request.json.get('count', 0)) == 0 and len(unanswered_questions) != 0:
        # first question of the session, new question is required
        question_id = unanswered_questions[0]
        question = handle.questions.find_one({"_id": ObjectId(unicode(question_id))})
        if question == None:
            abort(404)
    elif len(unanswered_questions) != 0:
        # not the first question and there are still new questions, can get either a new or review question
        type_question = probabilityOfNewQuestion(0.5)
        if type_question == True:
            question_id = unanswered_questions[0]
            question = handle.questions.find_one({"_id": ObjectId(unicode(question_id))})
            if question == None:
                abort(404)
        else:
            # review question, use leitner box
            if len(user_questions) != 0:
                question_id = leitnerBoxSelection(user_questions)
                question = handle.questions.find_one({"_id": ObjectId(unicode(question_id))})
                if question == None:
                    abort(404)
            else:
                question_id = unanswered_questions[0]
                question = handle.questions.find_one({"_id": ObjectId(unicode(question_id))})
                if question == None:
                    abort(404) 
    else:
        # treat all questions as review questions... no themes yet
        if len(user_questions) != 0:
            question_id = leitnerBoxSelection(user_questions)
            question = handle.questions.find_one({"_id": ObjectId(unicode(question_id))})
            if question == None:
                abort(404)
        else:
            question_id = unanswered_questions[0]
            question = handle.questions.find_one({"_id": ObjectId(unicode(question_id))})
            if question == None:
                abort(404) 
    return jsonify(make_public_question(question))

### ERROR HANDLING ###
@app.errorhandler(404)
#@auth.login_required
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
