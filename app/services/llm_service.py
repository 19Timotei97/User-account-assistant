import logging

# Package imports
from abc import ABC, abstractmethod
from openai import OpenAIError, RateLimitError, AuthenticationError
from fastapi import HTTPException
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableSequence, RunnableLambda
from langchain.prompts import PromptTemplate
from langchain_core.messages.ai import AIMessage
from langchain_openai import ChatOpenAI
from langchain.schema.runnable import RunnableBranch

# Local files imports
from core.config import get_settings


"""
This module defines the Responder class and its subclasses, which are used to generate responses to questions.

The OpenAI_Responder class uses the OpenAI API and LangChain to route and respond to questions.
"""


# Set the logging config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Retrieve the environment variables as settings
settings = get_settings()


class Responder(ABC):
    """
    Base class for responding to questions.
    """
    @abstractmethod
    def get_response(self, prompt: str) -> str:
        """
        Generates a response to a prompt.

        :param prompt: The prompt to generate a response for.
        :return: The generated response.
        """
        raise NotImplementedError("Subclasses must implement this method")


class OpenAI_Responder(Responder):
    """
    Uses the OpenAI API and LangChain to route and respond to questions.
    """
    def __init__(
            self, 
            model_name: str = "gpt-3.5-turbo",
            max_tokens: int = 100,
            n: int = 1,
            temperature: float = 0.3
        ) -> None:
        """
        Initializes the OpenAI_Responder class.

        :param max_tokens: The maximum number of tokens to generate.
        :param n: The number of responses to generate.
        :param temperature: The temperature to use for sampling.
        :return: None
        """
        self.openai_api_key = settings.openai_api_key

        if not self.openai_api_key:
            raise EnvironmentError("OPENAI_API_KEY environment variable is not set!")

        self.model_name = model_name
        self.max_tokens = max_tokens
        self.n = n
        self.temperature = temperature
        self.init_router()


    def init_router(self) -> None:
        """
        Initializes the router for the OpenAI_Responder class.
        """
        router_prompt = PromptTemplate.from_template(
            """Given the following question, determine if it's related to IT support / account management or not.
            Classify it as either `IT` if it is or `NON_IT` if it's not. "
            
            Examples:

            <question>
            How do I reset my password?
            </question>
            Classification: IT

            <question>
            Can I get a discount if I buy a lot of stuff?
            </question>
            Classification: NON_IT

            Do not respond with more than this classification.
            
            <question>
            {question}
            </question>
            Classification:"""
        )

        # Define a router model for the question classification task
        router_model = ChatOpenAI(
            model_name=self.model_name,
            temperature=0, 
            openai_api_key=self.openai_api_key
        )

        # Define the router chain with the prompt, model and the output parser
        self.router_chain = router_prompt | router_model | StrOutputParser()

        # Define the IT related question handling
        it_prompt = PromptTemplate.from_template(
            """You are an expert in IT support and account management.

            You answer only to this kind of questions and nothing more.

            Provide a short but helpful answer.

            Question: {question}
            Answer:"""
        )

        it_model = ChatOpenAI(
            model_name=self.model_name,
            temperature=self.temperature, 
            max_tokens=self.max_tokens, 
            n=self.n, 
            openai_api_key=self.openai_api_key
        )

        # Define the IT question answering chain
        self.it_chain = it_prompt | it_model

        # Define a compliance chain that will be used in case the user doesn't ask an IT related question.
        self.compliance_chain = PromptTemplate.from_template(
            """Simply provide the following answer to the following question.

            Refuse to give any tips or advice. Only provide the answer.

            Question: {question}
            Answer: This is not really what I was trained for, therefore I cannot answer. Try again."""
        ) | router_model
        
        # Create the runnable branch
        self.branch = RunnableBranch(
            (lambda x: "IT" in x["topic"].upper(), self.it_chain),
            (lambda x: "NON_IT" in x["topic"].upper(), self.compliance_chain),
            self.compliance_chain
        )

        # Finally, prepare the full chain, which will deal with the question
        self.full_chain = {
            "topic": self.router_chain,
            "question": lambda x: x["question"]
        } | self.branch


    def get_response(self, prompt: str) -> str:
        """
        Generates a response to a prompt using the OpenAI API.
        The model also has a system prompt which guides the assistant on how to respond.

        :param prompt: The prompt to generate a response for.
        :return: The generated response.
        """
        try:
            response = self.full_chain.invoke({
                "question": prompt
            })

            # Ensure the response is an AIMessage and return its content
            if isinstance(response, AIMessage):
                return response.content
            else:
                # Handle unexpected response types
                raise HTTPException(status_code=500, detail="Unexpected response type received.")
        
        except AuthenticationError as authentication_excep:
            logging.error(f"AuthenticationError: {authentication_excep}")
            # 401 - Invalid Authentication
            raise HTTPException(status_code=401, detail=str(authentication_excep)) from authentication_excep
        
        except RateLimitError as rate_limit_excep:
            logging.error(f"RateLimitError: {rate_limit_excep}")
            # 429 - Rate limit reached for requests
            raise HTTPException(status_code=429, detail=str(rate_limit_excep)) from rate_limit_excep
        
        except OpenAIError as openai_excep:
            logging.error(f"OpenAIError: {openai_excep}")
            # 500 - The server had an error while processing your request
            raise HTTPException(status_code=500, detail=str(openai_excep)) from openai_excep


    def route(self, info) -> RunnableSequence:
        """
        Using a custom function (Recommended).
        https://python.langchain.com/docs/how_to/routing/

        Routes the question to the appropriate chain based on the topic.

        :param info: The question to route.
        :return: The chain to use for the question.
        """
        if "IT" in info["topic"].upper():
            logging.info('Found IT in the info!')
            return self.it_chain
        
        elif "NON_IT" in info["topic"].upper():
            logging.info('Found NON_IT in the info!')
            return self.compliance_chain
        
        else:
            logging.info('Responding with the compliance chain!')
            return self.compliance_chain


    def get_routed_response(self, prompt: str) -> str:
        """
        Generates a response to a prompt using the OpenAI API and a custom routing function.

        :param prompt: The prompt to generate a response for.
        :return: The generated response.
        """
        full_routing_chain = {
            "topic": self.router_chain,
            "question": lambda x: x["question"]
        } | RunnableLambda(self.route)

        try:
            response = full_routing_chain.invoke({
                "question": prompt
            })

            # Ensure the response is an AIMessage and return its content
            if isinstance(response, AIMessage):
                return response.content
            else:
                # Handle unexpected response types
                raise HTTPException(status_code=500, detail="Unexpected response type received.")
        
        except AuthenticationError as authentication_excep:
            logging.error(f"AuthenticationError: {authentication_excep}")
            # 401 - Invalid Authentication
            raise HTTPException(status_code=401, detail=str(authentication_excep)) from authentication_excep
        
        except RateLimitError as rate_limit_excep:
            logging.error(f"RateLimitError: {rate_limit_excep}")
            # 429 - Rate limit reached for requests
            raise HTTPException(status_code=429, detail=str(rate_limit_excep)) from rate_limit_excep
        
        except OpenAIError as openai_excep:
            logging.error(f"OpenAIError: {openai_excep}")
            # 500 - The server had an error while processing your request
            raise HTTPException(status_code=500, detail=str(openai_excep)) from openai_excep
