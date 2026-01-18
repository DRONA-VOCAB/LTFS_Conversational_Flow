# LTFS Conversational Flow - Architecture & Flow Diagrams

## 1. System Architecture Overview

```mermaid
graph TB
    subgraph "Frontend (React + Vite)"
        UI[React UI Components]
        WS_CLIENT[WebSocket Client]
        AUDIO_PROC[Audio Processing]
        PCM_PLAYER[PCM Audio Player]
        API_CLIENT[REST API Client]
    end

    subgraph "Backend (FastAPI + Python)"
        MAIN[FastAPI Main App]
        WS_HANDLER[WebSocket Handler]
        ROUTES[REST API Routes]
        
        subgraph "Core Services"
            FLOW_MGR[Flow Manager]
            CONV_FLOW[Conversational Flow]
            SESSION_MGR[Session Manager]
        end
        
        subgraph "Audio Pipeline"
            VAD[Voice Activity Detection]
            ASR_SVC[ASR Service]
            TTS_SVC[TTS Service]
        end
        
        subgraph "Data Layer"
            SESSION_STORE[Session Store]
            DB_CONFIG[Database Config]
        end
        
        subgraph "AI/LLM"
            GEMINI[Gemini LLM Client]
            QUESTIONS[Question Handlers]
            SUMMARY[Summary Service]
        end
        
        subgraph "Queue System"
            ASR_Q[ASR Queue]
            TTS_Q[TTS Queue]
            LLM_Q[LLM Queue]
        end
    end

    subgraph "External Services"
        ASR_API[ASR API Server<br/>Port 5073]
        TTS_API[TTS API Server<br/>Port 5060]
        GEMINI_API[Google Gemini API]
        POSTGRES[PostgreSQL Database<br/>Neon Cloud]
    end

    %% Frontend Connections
    UI --> WS_CLIENT
    UI --> API_CLIENT
    WS_CLIENT --> AUDIO_PROC
    AUDIO_PROC --> PCM_PLAYER

    %% Backend Internal Connections
    MAIN --> WS_HANDLER
    MAIN --> ROUTES
    WS_HANDLER --> VAD
    WS_HANDLER --> SESSION_MGR
    
    VAD --> ASR_Q
    ASR_Q --> ASR_SVC
    ASR_SVC --> FLOW_MGR
    FLOW_MGR --> CONV_FLOW
    CONV_FLOW --> GEMINI
    FLOW_MGR --> TTS_Q
    TTS_Q --> TTS_SVC
    
    ROUTES --> SESSION_STORE
    ROUTES --> DB_CONFIG
    SESSION_MGR --> SESSION_STORE
    FLOW_MGR --> QUESTIONS
    FLOW_MGR --> SUMMARY

    %% External API Connections
    WS_CLIENT -.->|WebSocket| WS_HANDLER
    API_CLIENT -.->|HTTP/REST| ROUTES
    ASR_SVC -.->|HTTP| ASR_API
    TTS_SVC -.->|HTTP| TTS_API
    GEMINI -.->|HTTP| GEMINI_API
    DB_CONFIG -.->|PostgreSQL| POSTGRES

    %% Styling
    classDef frontendNode fill:#e1f5fe
    classDef backendNode fill:#f3e5f5
    classDef externalNode fill:#fff3e0
    classDef coreNode fill:#e8f5e8
    classDef audioNode fill:#fce4ec
    classDef aiNode fill:#f1f8e9

    class UI,WS_CLIENT,AUDIO_PROC,PCM_PLAYER,API_CLIENT frontendNode
    class MAIN,WS_HANDLER,ROUTES backendNode
    class FLOW_MGR,CONV_FLOW,SESSION_MGR coreNode
    class VAD,ASR_SVC,TTS_SVC,ASR_Q,TTS_Q,LLM_Q audioNode
    class GEMINI,QUESTIONS,SUMMARY aiNode
    class ASR_API,TTS_API,GEMINI_API,POSTGRES externalNode
```

## 2. Audio Processing Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant WebSocket
    participant VAD
    participant ASR
    participant LLM
    participant TTS
    participant AudioPlayer

    User->>Frontend: Speaks into microphone
    Frontend->>Frontend: Capture audio (16kHz PCM)
    Frontend->>WebSocket: Send audio chunks
    WebSocket->>VAD: Process audio frames
    VAD->>VAD: Detect speech activity
    
    alt Speech Detected
        VAD->>ASR: Send audio buffer
        ASR->>ASR: Transcribe speech
        ASR->>LLM: Send transcription
        LLM->>LLM: Process conversation
        LLM->>TTS: Generate response text
        TTS->>TTS: Synthesize speech
        TTS->>WebSocket: Stream audio chunks
        WebSocket->>Frontend: Send audio data
        Frontend->>AudioPlayer: Play response (24kHz)
        AudioPlayer->>User: User hears response
    end
```

## 3. Conversational Flow Architecture

```mermaid
graph TD
    START[Session Start] --> IDENTITY[Identity Confirmation]
    IDENTITY --> |Confirmed| LOAN_CHECK[Loan Verification]
    IDENTITY --> |Wrong Person| AVAILABILITY[Check Availability]
    AVAILABILITY --> END_WRONG[End Call - Wrong Person]
    
    LOAN_CHECK --> |Has Loan| PAYMENT_CHECK[Payment Made?]
    LOAN_CHECK --> |No Loan| END_NO_LOAN[End Call - No Loan]
    
    PAYMENT_CHECK --> |Yes| COLLECT_DETAILS[Collect Payment Details]
    PAYMENT_CHECK --> |No| END_NO_PAYMENT[End Call - No Payment]
    
    COLLECT_DETAILS --> PAYEE[Who Made Payment?]
    PAYEE --> DATE[Payment Date]
    DATE --> MODE[Payment Mode]
    MODE --> REASON[Payment Reason]
    REASON --> AMOUNT[Payment Amount]
    
    AMOUNT --> SUMMARY[Generate Summary]
    SUMMARY --> CONFIRM[User Confirmation]
    CONFIRM --> |Confirmed| CLOSING[Closing Statement]
    CONFIRM --> |Edit Required| EDIT[Edit Information]
    EDIT --> SUMMARY
    
    CLOSING --> END_SUCCESS[End Call - Success]

    %% Styling
    classDef startNode fill:#c8e6c9
    classDef processNode fill:#bbdefb
    classDef decisionNode fill:#fff9c4
    classDef endNode fill:#ffcdd2

    class START startNode
    class IDENTITY,LOAN_CHECK,PAYMENT_CHECK,COLLECT_DETAILS,PAYEE,DATE,MODE,REASON,AMOUNT,SUMMARY,CONFIRM,EDIT,CLOSING processNode
    class END_WRONG,END_NO_LOAN,END_NO_PAYMENT,END_SUCCESS endNode
```

## 4. Data Flow Architecture

```mermaid
graph LR
    subgraph "Input Layer"
        VOICE[Voice Input]
        REST[REST Requests]
    end
    
    subgraph "Processing Layer"
        ASR[Speech Recognition]
        NLP[Natural Language Processing]
        FLOW[Conversation Flow Logic]
    end
    
    subgraph "AI Layer"
        GEMINI[Gemini LLM]
        QUESTIONS[Question Processing]
        SUMMARY_AI[Summary Generation]
    end
    
    subgraph "Storage Layer"
        SESSION[Session Data]
        CUSTOMER[Customer Database]
        LOGS[Conversation Logs]
    end
    
    subgraph "Output Layer"
        TTS[Text-to-Speech]
        JSON[JSON Responses]
    end

    VOICE --> ASR
    REST --> FLOW
    ASR --> NLP
    NLP --> FLOW
    FLOW --> GEMINI
    FLOW --> QUESTIONS
    GEMINI --> SUMMARY_AI
    QUESTIONS --> SESSION
    FLOW --> SESSION
    SESSION --> CUSTOMER
    FLOW --> LOGS
    SUMMARY_AI --> TTS
    FLOW --> JSON
    TTS --> VOICE
    JSON --> REST

    %% Styling
    classDef inputNode fill:#e3f2fd
    classDef processingNode fill:#f3e5f5
    classDef aiNode fill:#e8f5e8
    classDef storageNode fill:#fff3e0
    classDef outputNode fill:#fce4ec

    class VOICE,REST inputNode
    class ASR,NLP,FLOW processingNode
    class GEMINI,QUESTIONS,SUMMARY_AI aiNode
    class SESSION,CUSTOMER,LOGS storageNode
    class TTS,JSON outputNode
```

## 5. Component Interaction Diagram

```mermaid
graph TB
    subgraph "Frontend Components"
        CHATBOT[Chatbot Component]
        AUDIO_HOOKS[Audio Hooks]
        API_SERVICE[API Service]
    end
    
    subgraph "Backend Core"
        MAIN_APP[FastAPI Main]
        WS_ENDPOINT[WebSocket Endpoint]
        REST_ROUTES[REST Routes]
    end
    
    subgraph "Session Management"
        SESSION_SCHEMA[Session Schema]
        SESSION_STORE[Session Store]
        SESSION_MANAGER[Session Manager]
    end
    
    subgraph "Question System"
        Q1[Q1: Identity]
        Q2[Q2: Availability]
        Q3[Q3: Loan Taken]
        Q4[Q4: EMI Payment]
        Q5[Q5: Payee]
        Q6[Q6: Payee Details]
        Q7[Q7: Payment Date]
        Q8[Q8: Payment Mode]
        Q9[Q9: Executive Details]
        Q10[Q10: Payment Reason]
        Q11[Q11: Amount]
    end
    
    subgraph "AI Processing"
        FLOW_MANAGER[Flow Manager]
        CONV_AI[Conversational AI]
        GEMINI_CLIENT[Gemini Client]
    end
    
    subgraph "Audio Pipeline"
        VAD_SILERO[VAD Silero]
        ASR_SERVICE[ASR Service]
        TTS_SERVICE[TTS Service]
    end

    CHATBOT --> AUDIO_HOOKS
    CHATBOT --> API_SERVICE
    AUDIO_HOOKS --> WS_ENDPOINT
    API_SERVICE --> REST_ROUTES
    
    WS_ENDPOINT --> SESSION_MANAGER
    WS_ENDPOINT --> VAD_SILERO
    REST_ROUTES --> SESSION_STORE
    
    VAD_SILERO --> ASR_SERVICE
    ASR_SERVICE --> FLOW_MANAGER
    FLOW_MANAGER --> CONV_AI
    CONV_AI --> GEMINI_CLIENT
    FLOW_MANAGER --> Q1
    FLOW_MANAGER --> Q2
    FLOW_MANAGER --> Q3
    FLOW_MANAGER --> Q4
    FLOW_MANAGER --> Q5
    FLOW_MANAGER --> Q6
    FLOW_MANAGER --> Q7
    FLOW_MANAGER --> Q8
    FLOW_MANAGER --> Q9
    FLOW_MANAGER --> Q10
    FLOW_MANAGER --> Q11
    
    FLOW_MANAGER --> TTS_SERVICE
    SESSION_MANAGER --> SESSION_SCHEMA
    SESSION_STORE --> SESSION_SCHEMA
```

## 6. Technology Stack

```mermaid
graph TB
    subgraph "Frontend Stack"
        REACT[React 18]
        VITE[Vite Build Tool]
        TAILWIND[Tailwind CSS]
        AXIOS[Axios HTTP Client]
        WS_API[WebSocket API]
    end
    
    subgraph "Backend Stack"
        FASTAPI[FastAPI Framework]
        PYTHON[Python 3.12]
        UVICORN[Uvicorn ASGI Server]
        ASYNCIO[AsyncIO]
        WEBSOCKETS[WebSockets]
    end
    
    subgraph "AI/ML Stack"
        GEMINI_AI[Google Gemini 2.0]
        SILERO[Silero VAD]
        TORCH[PyTorch]
        NUMPY[NumPy]
    end
    
    subgraph "Database Stack"
        POSTGRESQL[PostgreSQL]
        NEON[Neon Cloud DB]
        PSYCOPG2[Psycopg2 Driver]
    end
    
    subgraph "Audio Stack"
        PCM[PCM Audio Format]
        WEBAUDIO[Web Audio API]
        WORKLETS[Audio Worklets]
    end
    
    subgraph "External APIs"
        ASR_EXT[External ASR API]
        TTS_EXT[External TTS API]
        GEMINI_EXT[Gemini API]
    end

    %% Connections
    REACT --> VITE
    REACT --> TAILWIND
    REACT --> AXIOS
    REACT --> WS_API
    
    FASTAPI --> PYTHON
    FASTAPI --> UVICORN
    FASTAPI --> ASYNCIO
    FASTAPI --> WEBSOCKETS
    
    GEMINI_AI --> TORCH
    SILERO --> TORCH
    TORCH --> NUMPY
    
    POSTGRESQL --> NEON
    NEON --> PSYCOPG2
    
    PCM --> WEBAUDIO
    WEBAUDIO --> WORKLETS
    
    %% External connections
    GEMINI_AI -.-> GEMINI_EXT
    FASTAPI -.-> ASR_EXT
    FASTAPI -.-> TTS_EXT
```

## 7. Deployment Architecture

```mermaid
graph TB
    subgraph "Client Side"
        BROWSER[Web Browser]
        MOBILE[Mobile Browser]
    end
    
    subgraph "Load Balancer"
        NGINX[Nginx Reverse Proxy]
    end
    
    subgraph "Application Server"
        FRONTEND_STATIC[Static Frontend Files]
        BACKEND_API[FastAPI Backend]
        WS_SERVER[WebSocket Server]
    end
    
    subgraph "External Services"
        ASR_SERVER[ASR Server<br/>27.111.72.52:5073]
        TTS_SERVER[TTS Server<br/>27.111.72.52:5060]
        GEMINI_CLOUD[Google Gemini API]
    end
    
    subgraph "Database"
        NEON_DB[Neon PostgreSQL<br/>Cloud Database]
    end
    
    subgraph "Monitoring & Logs"
        LATENCY[Latency Tracking]
        LOGS[Application Logs]
        METRICS[Performance Metrics]
    end

    BROWSER --> NGINX
    MOBILE --> NGINX
    NGINX --> FRONTEND_STATIC
    NGINX --> BACKEND_API
    NGINX --> WS_SERVER
    
    BACKEND_API --> ASR_SERVER
    BACKEND_API --> TTS_SERVER
    BACKEND_API --> GEMINI_CLOUD
    BACKEND_API --> NEON_DB
    
    WS_SERVER --> ASR_SERVER
    WS_SERVER --> TTS_SERVER
    WS_SERVER --> GEMINI_CLOUD
    
    BACKEND_API --> LATENCY
    WS_SERVER --> LOGS
    BACKEND_API --> METRICS
```

## 8. Security & Configuration

```mermaid
graph LR
    subgraph "Environment Configuration"
        ENV_VARS[Environment Variables]
        API_KEYS[API Keys]
        DB_CREDS[Database Credentials]
    end
    
    subgraph "Security Layers"
        CORS[CORS Configuration]
        SSL[SSL/TLS]
        AUTH[Authentication]
        RATE_LIMIT[Rate Limiting]
    end
    
    subgraph "Data Protection"
        ENCRYPTION[Data Encryption]
        PII_MASK[PII Masking]
        SECURE_CONN[Secure Connections]
    end

    ENV_VARS --> API_KEYS
    ENV_VARS --> DB_CREDS
    API_KEYS --> CORS
    DB_CREDS --> SSL
    CORS --> AUTH
    SSL --> RATE_LIMIT
    AUTH --> ENCRYPTION
    RATE_LIMIT --> PII_MASK
    ENCRYPTION --> SECURE_CONN
```

## Key Features & Capabilities

### Real-time Audio Processing
- **16kHz PCM input** for speech recognition
- **24kHz PCM output** for text-to-speech
- **Voice Activity Detection** using Silero VAD
- **Streaming audio** with WebSocket communication

### Intelligent Conversation Flow
- **Dynamic question routing** based on responses
- **Context-aware processing** with session management
- **Multi-language support** (Hindi/English/Hinglish)
- **Fallback mechanisms** for unclear responses

### Scalable Architecture
- **Microservices design** with queue-based processing
- **Async/await patterns** for high concurrency
- **External API integration** for ASR/TTS services
- **Cloud database** with connection pooling

### Monitoring & Analytics
- **Latency tracking** for performance optimization
- **Conversation logging** for quality assurance
- **Error handling** with graceful degradation
- **Real-time metrics** collection