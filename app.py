#!flask/bin/python
from flask import Flask, jsonify, abort, make_response, request, url_for
from flask.ext.httpauth import HTTPBasicAuth
import os
from pymongo import MongoClient
from bson.objectid import ObjectId
import keys

### MONGO CONNECTION ###
def connect():
    mongo_keys = keys.mongoKeys()
    connection = MongoClient(mongo_keys[0],mongo_keys[1])
    handle = connection[mongo_keys[2]]
    handle.authenticate(mongo_keys[3],mongo_keys[4])
    return handle


app = Flask(__name__)
auth = HTTPBasicAuth()
handle = connect()


#### HELPER FUNCTIONS ####
def make_public_question(question):
    '''Making public uris for questions'''
    new_question = {}
    for field in question:
        if field == '_id':
            new_question['uri'] = url_for('get_question', question_id=question['_id'], _external=True)
        else:
            new_question[field] = question[field]
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

def calculate_difficulty(bool_answer, current_difficulty):
    int_answer = -1
    if bool_answer == False:
        int_answer = 1
    if current_difficulty >= 4 and int_answer > 0:
        pass
    elif current_difficulty <= 1 and int_answer < 1:
        pass
    else:
        current_difficulty = current_difficulty + int_answer
    print current_difficulty
    return current_difficulty

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


#### ROUTES ####

# QUESTION ROUTES [DATA ENTRY]
@app.route('/askii/api/v1.0/questions', methods=['GET'])
@auth.login_required
def get_questions():
    '''Get a list of all questions'''
    return jsonify({'questions': [make_public_question(question) for question in handle.questions.find()]})

@app.route('/askii/api/v1.0/questions/<question_id>', methods=['GET'])
@auth.login_required
def get_question(question_id):
    '''Get a question by _id'''
    question = handle.questions.find_one({"_id": ObjectId(unicode(question_id))})
    if question == None:
        abort(404)
    return jsonify({'question': make_public_question(question)})

@app.route('/askii/api/v1.0/questions', methods=['POST'])
@auth.login_required
def create_question():
    '''Create new question and append to end of question list'''
    if not request.json or not 'question' in request.json:
        abort(400)
    order_obj = handle.order.find()[0]
    order_id = order_obj["_id"]
    order_list = order_obj["order"]
    question = {
        'question': request.json['question'],
        'answer': request.json.get('answer', ""),
        'content': request.json.get('content', ""),
        'hint': request.json.get('hint', ""),
        'regex': request.json.get('regex', ""),
        'difficulty': request.json.get('difficulty', 0)
    }
    handle.questions.insert(question)
    index = request.json.get('index', None)
    if index == None:
        order_list.append(unicode(question["_id"]))
    else:
        order_list.insert(index, unicode(question["_id"]))
    writeResponse = handle.order.update({"_id": ObjectId(unicode(order_id))}, {"order": order_list})
    if int(writeResponse.get('nModified', 0)) == 0:
        abort(404)
    return jsonify({'question': make_public_question(question)}), 201

@app.route('/askii/api/v1.0/questions/<question_id>', methods=['PUT'])
@auth.login_required
def update_question(question_id):
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
    writeResponse = handle.questions.update({"_id": ObjectId(unicode(question_id))}, updated_question_fields)
    if int(writeResponse.get('nModified', 0)) == 0:
        abort(404)
    question = updated_question_fields.copy()
    question.update({"_id": question_id})
    return jsonify({'question': make_public_question(question)})

@app.route('/askii/api/v1.0/questions/<question_id>', methods=['DELETE'])
@auth.login_required
def delete_question(question_id):
    '''Delete a question by _id'''
    deleteResponse = handle.questions.remove({"_id": ObjectId(unicode(question_id))})
    if int(deleteResponse.get('n', 0)) == 0:
        abort(404)
    return jsonify({'result': True})

# USER FUNCTIONS
@app.route('/askii/api/v1.0/users', methods=['GET'])
@auth.login_required
def get_users():
    '''Get a list of all users'''
    # return jsonify({'questions': [make_public_question(question) for question in handle.questions.find()]})
    return jsonify({'users': [make_public_user(user) for user in handle.users.find()]})

@app.route('/askii/api/v1.0/users/<user_id>', methods=['GET'])
@auth.login_required
def get_user(user_id):
    '''Get a user by _id'''
    user = handle.users.find_one({"_id": ObjectId(unicode(user_id))})
    if user == None:
        abort(404)
    return jsonify({'user': make_public_user(user)})

@app.route('/askii/api/v1.0/users', methods=['POST'])
@auth.login_required
def create_user():
    '''Create new user and append to end of user list'''
    if not request.json or not 'name' in request.json:
        abort(400)
    user = {
        'name': request.json['name'],
        'questions' : {}
    }
    handle.users.insert(user)
    return jsonify({'user': make_public_user(user)}), 201

@app.route('/askii/api/v1.0/users/<user_id>', methods=['PUT'])
@auth.login_required
def update_user(user_id):
    '''Update a user by _id'''
    updated_user_fields = {}
    if not request.json:
        abort(400)
    if 'name' in request.json and type(request.json['name']) != unicode:
        abort(400)
    if request.json.get('name', None) != None:
        updated_user_fields['name'] = request.json['name']
    writeResponse = handle.users.update({"_id": ObjectId(unicode(user_id))}, updated_user_fields)
    if int(writeResponse.get('nModified', 0)) == 0:
        abort(404)
    user = updated_user_fields.copy()
    user.update({"_id": user_id})
    return jsonify({'user': make_public_user(user)})

@app.route('/askii/api/v1.0/users/<user_id>', methods=['DELETE'])
@auth.login_required
def delete_user(user_id):
    '''Delete a user by _id'''
    deleteResponse = handle.users.remove({"_id": ObjectId(unicode(user_id))})
    if int(deleteResponse.get('n', 0)) == 0:
        abort(404)
    return jsonify({'result': True})


### GET AND ANSWER QUESTIONS ###
@app.route('/askii/api/v1.0/users/<user_id>/<question_id>', methods=['PUT'])
@auth.login_required
def answer_question(user_id, question_id):
    user = handle.users.find_one({"_id": ObjectId(unicode(user_id))})
    question = handle.questions.find_one({"_id": ObjectId(unicode(question_id))})
    user_questions = user["questions"]
    already_answered_question = user_questions.get(question_id, None)

    if not request.json:
        abort(400)
    if 'answer' in request.json and type(request.json['answer']) != unicode:
        abort(400)
    if request.json.get('answer', None) != None:
        answer = bool(int(request.json['answer']))
        if already_answered_question == None:
            calculate_difficulty(answer, int(question.get("difficulty", 0)))
        else:
            calculate_difficulty(answer, int(user_questions[question_id]["difficulty"]))
    else:
        abort(404)
    return 'done'


### ERROR HANDLING ###
@app.errorhandler(404)
@auth.login_required
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)

if __name__ == '__main__':
    app.run(debug=True)