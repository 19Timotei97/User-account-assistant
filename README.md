# Contextual FAQ Assistant

![Image](screenshots/contextual_FAQ.gif)

## Important disclaimer!!
If you want to run the app, you **MUST** define the environment variables inside the .env.example. After that, you can rename it to _.env_ and simply run _docker-compose up --build_ and it _should_ :) work with no issues.
One thing I haven't quite get past is that the app address is _localhost:8080_, and not Docker's _0.0.0.0:8080_. From what I understood, it makes the app listen for connections from any IP address, handling requests from the host machine.

## Short presentation
This simple application implements an assistant for frequently asked user questions regarding IT support or account management.
It uses a Postgres database to store and retrieve embeddings of a series of provided questions and answers, and also updates the embeddings during usage, in order to enhance the responses accuracy and duration.

A simple HTML page handles the login and authentication of the user (for testing purposes, I've used the _username_ "user" and the _password_ "test"); should this app be used in a production environment, **MUCH** better user management and password best practices need to be implemented.

![Image](screenshots/login_page.PNG)

I've tried to implement a full dark mode switcher, but I only managed to change the login card theme. You can understand then that I'm not a Web developer, nor that I try to become one.

![Image](screenshots/login_page_dark_mode.PNG)

After the user is logged in, he can start question the assistant with IT questions. A LangChain RunnableBranch is used to differentiate IT from NON-IT questions, but something stops it from being **extremely accurate**, as much prompt engineering and template instructions I've implemented.

![Image](screenshots/main_page.PNG)

It can answer IT questions pretty well, as seen from the following screenshot, as it detects that a question should be answered using the local database:

![Image](screenshots/it_qa.PNG)

It can also prompt the OpenAI model when it doesn't retrieve a close enough embedding:

![Image](screenshots/openai_qa.PNG)

But it can fail to completely refuse to respond to non IT-related questions (still something that I have to look into), even though the LangChain... ugh.. chain should deal with these kind of questions.

![Image](screenshots/fail_qa.PNG)


## Project structure

The project follows the following structure:

```bash
contextual_faq_assistant/
│
├── app/
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── auth.py    # Authentication logic
│   │
│   ├── celery_config/
│   │   ├── __init__.py
│   │   ├── tasks.py   # Celery configuration
│   │
│   ├── database/
│   │   ├── create_database.py  # Database creation
│   │   ├── manage_database.py  # Read, Update, Delete for embeddings
│   │   ├── manage_collections.py # Read, Update, Delete for collections
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── embeddings_service.py  # The Embeddings model
│   │   ├── llm_service.py         # The LangChain chain and OpenAI model
│   │
│   ├── templates/
│   │   ├── login.html    # Serves the login page
│   │   ├── question.html # Serves the QA page
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── utils.py          # Different utility functions
│   │   ├── FAQ_database.json # Provided FAQ database
│   │
│   ├── __init__.py
│   ├── main.py     # Entry point for the app
│
├── screenshots/        # Screenshots for this file
│── .env.example        # Environment variables file, needs to be renamed to .env after setting it up
├── docker-compose.yml  # Defines the Docker services
├── Dockerfile          # The Docker image
├── README.md
├── requirements.txt    # The project's package requirements
```

When it comes to the folder structure, I've tried to keep it as logical and clean as possible. Hopefully I don't need to go into too much detail here, having named each script and folder as descriptive as possible.

1. The **auth** folder contains the script which deals with _Authentication on FastAPI's endpoints using its dependency mechanism (Depends(get_token))_. It creates, verifies and retrieves that token in order to let the user access the assistant.

2. The **celery_config** folder defines the _Celery_ app, mainly the _tasks.py_ script defining and configuring it. Having used it only for adding and updating embeddings asynchronously, it only autodiscovers the those tasks. I've used Redis as the backend message broker. It's also my first time using that, so I've learned something new :)

![Image](screenshots/celery_async.PNG)

3. The **database** folder deals with everything about the _PostgreSQL_ database, used for _info and embedding storage_. Since I've only wanted to create the PoC for such a complex app, I've only used the database for this, and not for user data storage (username, password, email etc.) Of course, this should be done in a production environment, but I think it will suffice for this assignment. I would personally used a vector database, like _Chroma_ or _Pinecone_ for the embeddings, but since we would also need to retrieve the answer, I understand the choice (even though the metadata of one of those options would work too, I think). The scripts included in this folder are responsible for:

    3.1 Creating the initial _database_ and setting up the tables for storing the questions, their embeddings, their answers and the collection for each question.

    3.2 Managing the _database_, selecting the desired embeddings, inserting into the desired table with the corresponding values, updating values and potentially deleting embeddings and their data

    3.3 Managing the _collections_, should this is desired. I didn't used this script, since I only dealt with a single collection, but should more be needed, the implementation is there.

![Image](screenshots/postgresql.PNG)

4. The **services** folder is responsible with:

    4.1. Creating the embedding model, which also computes the embedding of a question  / prompt. It's implemented as a _singleton_ to avoid multiple initialization, it uses _caching_ to avoid multiple calls to the API, and it also _limits the token length_ for lengthy questions, using the _tiktoken_ tokenizer.

    4.2 Creating the OpenAI responder, implemented with a _LangChain RunnableBranch_, which theoretically deals with questions regarding IT or account management and refusing to respond to unrelated questions. As much as I tried, I didn't managed to completely make it refuse answering to such kind of questions, but the implementation is done according to the official documentation. I've even added the LangChain recommended implementation, which suggests using a route function instead of a now considered Legacy RunnableBranch. I'm happy that I created a helpful IT assistant, but I'm a bit sad that it's **WAY** too helpful.

5. The **templates** folder simply defines the _login.html_ page, used for user authentication and _question.html_ which is used throughout the application uptime. A lot of time went debugging this part, part of it being because of my lack of working with token authentication and part of it representing the passing of the token from the login page to the _ask-question_ FastAPI route. It was fun though, and I learned a lot.

6. Finally, the **utils** folder defines the _FAQ_database.json_ with the provided questions, and the _utils.py_ script, defining the utility functions. I hope the methods are descriptive enough for me not to go into details here.

7. The _main.py_ script is used for the FastAPI app, which first initializes the database, and stores the initial FAQ embeddings, deals with the token authentication and also serves the question answering route. I hope the comments and method descriptions are fully describing the intent behind every one of them.

8. I've also used a _docker-compose.yml_ file to define the services used for the application, as well as the postgres volume used for storing the embeddings. It is highly dependent on the _.env_ file, which defines many environment variables, including the OpenAI API key and model params, celery backend, database authentication and the secret key used for token generation.

9. There is a _Dockerfile_ too, used for running the app as a Docker image, in conjunction with the _docker-compose.yml_ file. It uses the _python:3.8-slim_ image as base, it copies the necessary files, installs the requirements, correctly uses a non-root user (since celery can complain about it) and runs the main uvicorn app on port 8080.


## Things that can be improved
Of course, I'm not going to "get drunk with cold water", as we Romanians like to say. It is not a perfect app, from many points:
- As I said, I'm not storing user data in a separate database, or even separate collections of questions per user. I presume this would be needed in a real-life scenario.
- There is a possibility that if the Docker container is stopped, and the last page loaded was the QA one, if the user restarts the app, that token authentication is bypassed (could be tested, if the browser _localStorage_ is emptied)
- I probably haven't correctly defined all the FastAPI routes, being my first time working with it, but I've learned a lot about it.
- A vector database could have been used for the embeddings, since for similarity search, **ALL** embeddings are retrieved and the cosine similarity is used for getting the most similar embedding and the answer.
- Probably the embeddings are not that qualitative, since I've used the small text-embeddings OpenAI app. There is a probability that the dimensions are not enough to capture the full semantic meaning with this model.
- Even though I've added highly descriptive comments for the majority (if not all) scripts and their methods, maybe they aren't that descriptive for an untrained eye.
- A much better job could have been done on the HTML / CSS / JS side, I've only managed that thanks to ChatGPT and Claude :)
- The Celery configuration could be enhanced, by adding task namespacing, and even task serializer or time limits. I've only used configuration that I understood for now, but it sounds very interesting.


## Conclusion
I've implemented a **contextual FAQ assistant**, capable of either selecting the most appropiate response from a local database, based on a similarity score or prompt an online LLM for the answer. I've added authentication using **FastAPI's dependency mechanism**, **PostgreSQL** for storing and retrieving embeddings and their answers, **LangChain's RunnableBranch** for answering / refusing to answer (this part still needs some work, we'll put it into backlog), **Dockerfile** and **docker-compose.yml** for running it as a Docker image and **Celery** for async embeddings adding and updating.
As external assistants, I've used **ChatGPT** (it's really great with the newest _memory_ feature), **Claude** (which sometimes is annoying with its way too formal way of responding, as if he would cry with me too when I'm getting an error) and **Amazon's Q** for code completion (it's really great, it shortened the development time a lot!).
Regardless of the final answer, I'm very _proud_ of what I've achieved, having learned a lot, being exposed to a lot of (new and old) technologies and being motivated to do it.

## LE Updates!
1. Switched to an in-database similarity search, which makes use of pgvector's functionality for vector cosine operation. For more info, check the newly added `search_for_similarity_in_db` method inside `app/database/manage_database.py` script.

```sql
SELECT content, answer, 1 - (embedding <=> %s::vector) AS similarity
    FROM embeddings
    WHERE collection = %s
    ORDER BY similarity DESC
    LIMIT 1;
```

This should help in case the local database becomes quite large.

2. Will work on some improvements including:
* following the FastAPI structure, which is recommended here: https://fastapi.tiangolo.com/tutorial/bigger-applications/.
* better management of env variables through a setup such as: https://fastapi.tiangolo.com/advanced/settings/ **[DONE]**
* SQLAlchemy for managing DB resources in an ORM approach
* schemas moved in a separate module and not in the main API logic (main.py)
* endpoint output schemas to be used and objects directly from the DB served (in this particular example)