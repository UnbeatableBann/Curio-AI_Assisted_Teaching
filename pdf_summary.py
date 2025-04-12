from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains.question_answering import load_qa_chain
from dotenv import load_dotenv
import os

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

class PDFSummarizer:
    def __init__(self):
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GEMINI_API_KEY)

    def get_conversational_chain(self):
        prompt_template = """
        Answer the question as detailed as possible from the provided context, make sure to provide all the details, if the answer is not in
        provided context just say, "answer is not available in the context", don't provide the wrong answer\n\n
        Context:\n {context}?\n
        Question: \n{question}\n

        Answer:
        """

        model = ChatGoogleGenerativeAI(api_key=GEMINI_API_KEY, model="gemini-2.0-flash", temperature=0.3)
        prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
        
        # Updated chain_type to "map_reduce"
        chain = load_qa_chain(model, chain_type="stuff", prompt=prompt)

        return chain

    def user_input(self, user_question):
        new_db = FAISS.load_local("faiss_index", self.embeddings, allow_dangerous_deserialization=True)
        docs = new_db.similarity_search(user_question)

        chain = self.get_conversational_chain()
        response = chain.invoke({"input_documents": docs, "question": user_question})
        return response["output_text"]