from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.tools import BaseTool
from langchain_pinecone import PineconeVectorStore
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import AgentExecutor, create_tool_calling_agent
from pinecone import Pinecone
import os
from dotenv import load_dotenv
load_dotenv()

class TCAgent:
    def __init__(self, model, system_prompt, company: str):
        self.llm = ChatOpenAI(model=model, api_key=os.getenv("OPENAI_API_KEY"))
        self.vector_store = self._create_vector_store()
        self.company = company
        self.retriever_tool = self._create_retriever_tool()
        self.agent = self._create_agent(system_prompt=system_prompt)
    
    def invoke(self, query: str):
        sources = []
        for chunk in self.agent.stream({"input": query}, config={"run_name": "Invoke Agent"}):
            if "steps" in chunk:
                for doc in chunk['steps'][0].observation:
                    sources.append(int(doc.metadata['page']))
        return chunk, sources
    
    def _create_agent(self, system_prompt: str):
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    system_prompt,
                ),
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
        )
        tools = [self.retriever_tool]
        agent = create_tool_calling_agent(self.llm, tools, prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        return agent_executor

    def _create_retriever_tool(self):
        retriever = self.vector_store.as_retriever(search_kwargs={"filter": {"company": self.company}})
        class RetrieverTool(BaseTool):
            name: str = "retriever_tool"
            description: str = "Tool to find information in a annual report"

            def _run(self, query: str):
                results = retriever.invoke(query)
                return results
            
        return RetrieverTool()

    def _create_vector_store(self):
        index_name = os.getenv("PINECONE_INDEX")
        index = Pinecone(api_key=os.getenv("PINECONE_API_KEY")).Index(index_name)
        embedding = OpenAIEmbeddings(model=os.getenv("EMBEDDINGS"), api_key=os.getenv("OPENAI_API_KEY"))
        return PineconeVectorStore(index=index, embedding=embedding)