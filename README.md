# Askii
Askii is an open-source API for smart question/answer content

## Getting Started

### Get an API Key
Sign up for an account on Askii's website.
You can then find your API Key on your Askii dashboard.

### Create and Link your MongoDB
Please create a MongoDB on [MongoLab](https://mongolab.com/). Then please link your MongoLab database to Askii using your Askii dashboard. 

To get the MongoLab fields needed, go to your MongoLab portal. At the top of the homepage for your database, you should see the following shell code.

```shell
To connect using the shell:\n\nmongo <dbsubdomian>.mongolab.com:<dbnumber>/<dbid> -u <dbuser> -p <dbpassword>
```

Please pull out these fields in input them into your Askii dashboard. After doing this, please press the "Setup DB" button on the portal.

One this runs, you should be all set to start using Askii.

## Restful API Commands

### GET /questions?key=yourAppKey
Gets a list of all the questions in your Askii database

### GET /questions/<question_id>?key=yourAppKey
Gets a question by ID from your Askii database

### POST /questions?key=yourAppKey
Add a question to your Askii database

_Params:_ 
```json
{
	"question": "the question you would like to ask the learner [required]"
	"answer": "the correct answer to the question [required]"
	"difficulty": "a numerical string representing easy (0), medium (1), hard (2), or very hard (3)"
	"content": 
		"text": "textual content with the answer to the question embedded"
		"image_url": "url of an image that may give the answer"
	"hint": "a hint to the question"
	"regex": "a regex that evaluates the correct answer"
}
```
### PUT /questions/<question_id>?key=yourAppKey
Update a question in your Askii database by ID

_Params:_
```json
{
	"any param except ID": "new value"
}
```

### DELETE /questions/<question_id>?key=yourAppKey
Delete a question in your Askii database by ID

### GET /users?key=yourAppKey
Gets a list of users in your Askii database

### GET /users/<user_id>?key=yourAppKey
Gets a user in your Askii databse by ID

### POST /users?key=yourAppKey
Creates a new user

_Params:_
```json
{
	"phone_num" : "phone number",
	"name" : "Askii"
}
```

### POST /users/<user_id>?key=yourAppKey
Update a user in your Askii databse by ID

_Params:_
```json
{
	"any param except ID": "new value"
}
```

### DELETE /users/<user_id>?key=yourAppKey
Delete a users in your Askii database by ID

### POST /users/<user_id>/<question_id>?key=yourAppKey
Update a user in your Askii database when a user answers a question

_Params:_
```json
{
	"answer": "False (0) or true (1)"
}
```

### POST /next/<user_id>?key=yourAppKey
Fetch the next question for a user to study from

_Params:_
```json
{
	"count": "String of the number of questions answered in the learner's session"
}
```
