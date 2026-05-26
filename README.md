# AskMira: AI-Powered Foreign Credit Evaluation Assistant for Northeastern University

<div align="center">
  <img src="AskMira Logo.png" alt="AskMira Logo" width="200"/>
  <p><em>Streamlining Northeastern University's foreign credit evaluation process through AI</em></p>
  
  [![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
  [![Streamlit](https://img.shields.io/badge/Streamlit-1.44-red.svg)](https://streamlit.io/)
  [![RAG](https://img.shields.io/badge/RAG-Enabled-purple.svg)](https://arxiv.org/abs/2005.11401)
  [![Northeastern](https://img.shields.io/badge/Northeastern-FCE-red.svg)](https://www.northeastern.edu/)
</div>

## 📚 Overview

AskMira is a specialized AI-powered assistant developed for Northeastern's Foreign Credit Evaluation (FCE) department. It combines Retrieval Augmented Generation (RAG) technology with Northeastern's specific FCE regulations to help staff, faculty, and students navigate the complex world of international education credential evaluation efficiently and accurately.

### Key Features

- **Natural Language Queries**: Ask about international credentials in plain English
- **Interactive UI**: User-friendly Streamlit interface for intuitive interactions
- **API Access**: FastAPI backend for programmatic integration
- **Vector Search**: Pinecone-powered semantic search for accurate information retrieval
- **University-Aligned**: Designed specifically for Northeastern University's FCE department workflows

## 🚀 Getting Started

### Prerequisites

- Docker and Docker Compose
- AWS account with S3 access (for document storage)
- PostgreSQL (runs automatically as a Docker service — no manual install needed)
- OpenAI API key
- Pinecone API key and index

### Environment Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/AskMira.git
   cd AskMira
   ```

2. Create a `.env` file in the project root with your credentials:
   ```
   AWS_REGION=your-region
   S3_BUCKET=askmira-fce-project
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   OPENAI_API_KEY=your-openai-key
   PINECONE_API_KEY=your-pinecone-key
   PINECONE_ENV=your-pinecone-env
   PINECONE_INDEX=askmira-index
   FASTAPI_URL=http://fastapi:8000
   POSTGRES_HOST=postgres
   POSTGRES_PORT=5432
   POSTGRES_USER=askmira
   POSTGRES_PASSWORD=your-strong-password
   POSTGRES_DB=askmira_db
   SECRET_KEY=any-long-random-string-for-jwt
   ```

### Running Locally

Start the application using Docker Compose:

```
docker-compose up
```

Access the interfaces at:
- Streamlit UI: http://localhost:8501
- FastAPI: http://localhost:8000
- FastAPI Documentation: http://localhost:8000/docs

### Deployment to AWS EC2

For production deployment, follow these steps:

1. Launch an EC2 instance with ports 22, 80, 8000, and 8501 open
2. Install Docker and Docker Compose on the instance
3. Clone the repository and set up your `.env` file
4. Run `docker-compose up -d` to start in detached mode
5. Access your application at your EC2 public DNS

## 🏗 Architecture

AskMira uses a modern architecture combining multiple technologies:

```
┌──────────────┐     ┌───────────────┐     ┌───────────────┐
│   Streamlit  │─────▶    FastAPI    │─────▶   OpenAI API  │
│  Frontend UI │     │    Backend    │     │   (GPT-4o)    │
└──────────────┘     └───────┬───────┘     └───────────────┘
                             │
                     ┌───────▼───────┐     ┌───────────────┐
                     │    Pinecone   │◀────▶  AWS S3 &     │
                     │ Vector Search │     │   PostgreSQL  │
                     └───────────────┘     └───────────────┘
```

### Data Flow

1. Documents from AACRAO EDGE and Northeastern's FCE regulations are stored in AWS S3
2. Document text is processed, embedded, and indexed in Pinecone
3. User queries via Streamlit UI are sent to FastAPI backend
4. Queries are embedded and used for semantic search in Pinecone
5. Relevant context is retrieved and combined with the user query
6. OpenAI's GPT-4o generates accurate, context-informed responses

## 📊 Data Sources

AskMira leverages two primary data sources:

1. **AACRAO EDGE**: Comprehensive database of international education systems
2. **Northeastern FCE Regulations**: Northeastern University's proprietary rules and guidelines for foreign credit evaluation including equivalency tables, GPA conversion formulas, and institutional policies

## 🤖 RAG Implementation

The Retrieval Augmented Generation pipeline:

1. **Ingestion**: Documents are chunked, embedded, and stored in a Pinecone vector index
2. **Retrieval**: User queries are embedded and matched against the vector index
3. **Generation**: Retrieved context is combined with the user query for the LLM
4. **Response**: The LLM generates an accurate, contextualized answer

## 📝 Usage Examples

### Asking About International Credentials at Northeastern

```
Can you tell me about the Diploma degree offered by institutions in India?
```

### Querying Northeastern's FCE Regulations

```
Does Northeastern have any rules for processing backlog or failed marksheets?
```

### Checking Equivalency Information

```
What is Northeastern's equivalency for the Pharm.D. degree and a Postgraduate Diploma?
```

## 🛠 Project Structure

```
AskMira/
├── FastAPI/                # Backend API service
│   ├── __pycache__/
│   ├── .env
│   ├── jwtauth.py
│   └── main.py
├── Scripts/                # Data processing scripts
│   ├── .env
│   ├── convert_excel_to_txt.py
│   ├── convert_s3_docs_to_txt.py
│   ├── ingest_to_pinecone.py
│   ├── scrape_aacrao_edge.py
├── Streamlit/              # Frontend application
│   ├── __pycache__/
│   ├── .env
│   ├── AACROEDGE.py
│   ├── AskMirabot.py
│   ├── informationpage.py
│   ├── landing.py
│   └── main.py
├── .dockerignore
├── .env
├── docker-compose.yml
├── Dockerfile.fastapi
├── Dockerfile.streamlit
└── README.md
```

## 📈 Future Enhancements

- Multi-language support
- User feedback integration for continuous improvement
- Enhanced visualization of educational pathways
- Mobile application for on-the-go access
- Custom LLM fine-tuned for education credential evaluation

## 🙏 Acknowledgments

- Northeastern University's Foreign Credit Evaluation department for domain expertise and regulations
- AACRAO EDGE for international education data
- OpenAI for GPT models
- Pinecone for vector search capabilities
- AWS for cloud infrastructure

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contact

For questions or support regarding this application, please contact:
- Application Support: [guptaritik2203@gmail.com](guptaritik2203@gmail.com)
