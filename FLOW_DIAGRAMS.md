# LTFS Conversational Flow - Detailed Flow Diagrams

## 1. Complete User Journey Flow

```mermaid
flowchart TD
    START([User Opens Application]) --> LOAD_CUSTOMERS[Load Customer List from Database]
    LOAD_CUSTOMERS --> SELECT_CUSTOMER[User Selects Customer]
    SELECT_CUSTOMER --> CREATE_SESSION[Create New Session]
    CREATE_SESSION --> INIT_AUDIO[Initialize Audio System]
    INIT_AUDIO --> START_CONVERSATION[Start Conversation]
    
    START_CONVERSATION --> GREETING[Bot: Greeting with Customer Name]
    GREETING --> WAIT_RESPONSE[Wait for User Response]
    WAIT_RESPONSE --> PROCESS_AUDIO[Process Audio Input]
    
    PROCESS_AUDIO --> VAD_CHECK{Voice Activity Detected?}
    VAD_CHECK -->|No| WAIT_RESPONSE
    VAD_CHECK -->|Yes| ASR_PROCESS[Speech Recognition]
    
    ASR_PROCESS --> LLM_PROCESS[LLM Processing]
    LLM_PROCESS --> EXTRACT_DATA[Extract Information]
    EXTRACT_DATA --> UPDATE_SESSION[Update Session Data]
    UPDATE_SESSION --> CHECK_COMPLETE{All Info Collected?}
    
    CHECK_COMPLETE -->|No| NEXT_QUESTION[Generate Next Question]
    NEXT_QUESTION --> TTS_GENERATE[Generate Speech Response]
    TTS_GENERATE --> PLAY_AUDIO[Play Audio Response]
    PLAY_AUDIO --> WAIT_RESPONSE
    
    CHECK_COMPLETE -->|Yes| GENERATE_SUMMARY[Generate Summary]
    GENERATE_SUMMARY --> PRESENT_SUMMARY[Present Summary to User]
    PRESENT_SUMMARY --> WAIT_CONFIRMATION[Wait for Confirmation]
    
    WAIT_CONFIRMATION --> CONFIRM_CHECK{User Confirms?}
    CONFIRM_CHECK -->|No| EDIT_INFO[Allow Information Editing]
    EDIT_INFO --> GENERATE_SUMMARY
    CONFIRM_CHECK -->|Yes| CLOSING_STATEMENT[Generate Closing Statement]
    CLOSING_STATEMENT --> END_SUCCESS([End - Success])
    
    %% Error Paths
    PROCESS_AUDIO --> ERROR_AUDIO{Audio Error?}
    ERROR_AUDIO -->|Yes| ERROR_HANDLER[Handle Audio Error]
    ERROR_HANDLER --> WAIT_RESPONSE
    
    LLM_PROCESS --> ERROR_LLM{LLM Error?}
    ERROR_LLM -->|Yes| FALLBACK_RESPONSE[Generate Fallback Response]
    FALLBACK_RESPONSE --> TTS_GENERATE
    
    %% Early Exit Paths
    LLM_PROCESS --> WRONG_PERSON{Wrong Person?}
    WRONG_PERSON -->|Yes| END_WRONG([End - Wrong Person])
    
    LLM_PROCESS --> NO_LOAN{No Loan?}
    NO_LOAN -->|Yes| END_NO_LOAN([End - No Loan])
    
    LLM_PROCESS --> NO_PAYMENT{No Payment?}
    NO_PAYMENT -->|Yes| END_NO_PAYMENT([End - No Payment])

    %% Styling
    classDef startEndNode fill:#c8e6c9,stroke:#4caf50,stroke-width:2px
    classDef processNode fill:#bbdefb,stroke:#2196f3,stroke-width:2px
    classDef decisionNode fill:#fff9c4,stroke:#ff9800,stroke-width:2px
    classDef errorNode fill:#ffcdd2,stroke:#f44336,stroke-width:2px
    classDef audioNode fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px

    class START,END_SUCCESS,END_WRONG,END_NO_LOAN,END_NO_PAYMENT startEndNode
    class LOAD_CUSTOMERS,SELECT_CUSTOMER,CREATE_SESSION,GREETING,ASR_PROCESS,LLM_PROCESS,EXTRACT_DATA,UPDATE_SESSION,NEXT_QUESTION,GENERATE_SUMMARY,PRESENT_SUMMARY,CLOSING_STATEMENT,EDIT_INFO processNode
    class VAD_CHECK,CHECK_COMPLETE,CONFIRM_CHECK,ERROR_AUDIO,ERROR_LLM,WRONG_PERSON,NO_LOAN,NO_PAYMENT decisionNode
    class ERROR_HANDLER,FALLBACK_RESPONSE errorNode
    class INIT_AUDIO,PROCESS_AUDIO,TTS_GENERATE,PLAY_AUDIO,WAIT_RESPONSE,WAIT_CONFIRMATION audioNode
```

## 2. Audio Processing Pipeline Flow

```mermaid
sequenceDiagram
    participant User as 👤 User
    participant Frontend as 🖥️ Frontend
    participant WebSocket as 🔌 WebSocket
    participant VAD as 🎙️ VAD Service
    participant ASR as 🗣️ ASR Service
    participant FlowMgr as 🧠 Flow Manager
    participant LLM as 🤖 Gemini LLM
    participant TTS as 🔊 TTS Service
    participant AudioPlayer as 🎵 Audio Player

    Note over User,AudioPlayer: Audio Processing Pipeline

    User->>Frontend: Speaks into microphone
    Frontend->>Frontend: Capture audio at 16kHz PCM
    Frontend->>WebSocket: Send audio chunks (320 samples)
    
    WebSocket->>VAD: Process audio frame
    VAD->>VAD: Analyze speech probability
    
    alt Speech Detected (probability > threshold)
        VAD->>VAD: Buffer audio data
        Note over VAD: Continue buffering until silence
        VAD->>ASR: Send complete utterance
        ASR->>ASR: Transcribe audio to text
        ASR->>FlowMgr: Send transcription
        
        FlowMgr->>FlowMgr: Determine conversation stage
        FlowMgr->>LLM: Process with context
        LLM->>LLM: Generate response & extract data
        LLM->>FlowMgr: Return structured response
        
        FlowMgr->>FlowMgr: Update session data
        FlowMgr->>TTS: Send response text
        TTS->>TTS: Synthesize speech at 24kHz
        TTS->>WebSocket: Stream audio chunks
        WebSocket->>Frontend: Forward audio data
        Frontend->>AudioPlayer: Play response audio
        AudioPlayer->>User: User hears response
    else No Speech Detected
        VAD->>WebSocket: Continue monitoring
    end
    
    Note over User,AudioPlayer: Cycle continues until conversation ends
```

## 3. Session Management Flow

```mermaid
stateDiagram-v2
    [*] --> SessionCreated: Create Session
    
    SessionCreated --> IdentityCheck: Start Conversation
    
    IdentityCheck --> IdentityConfirmed: Correct Person
    IdentityCheck --> CheckAvailability: Wrong Person
    IdentityCheck --> IdentityRetry: Unclear Response
    
    CheckAvailability --> EndWrongPerson: Not Available
    IdentityRetry --> IdentityCheck: Retry (Max 3)
    IdentityRetry --> EndMaxRetries: Max Retries Exceeded
    
    IdentityConfirmed --> LoanVerification: Identity OK
    
    LoanVerification --> PaymentCheck: Has Loan
    LoanVerification --> EndNoLoan: No Loan
    LoanVerification --> LoanRetry: Unclear Response
    
    LoanRetry --> LoanVerification: Retry
    LoanRetry --> EndMaxRetries: Max Retries
    
    PaymentCheck --> CollectDetails: Payment Made
    PaymentCheck --> EndNoPayment: No Payment
    PaymentCheck --> PaymentRetry: Unclear Response
    
    PaymentRetry --> PaymentCheck: Retry
    PaymentRetry --> EndMaxRetries: Max Retries
    
    CollectDetails --> PayeeCollection: Start Collection
    
    PayeeCollection --> PayeeDetailsCheck: Payee Identified
    PayeeCollection --> PayeeRetry: Unclear Response
    
    PayeeDetailsCheck --> DateCollection: Self Payment
    PayeeDetailsCheck --> PayeeDetails: Third Party Payment
    
    PayeeDetails --> DateCollection: Details Collected
    PayeeRetry --> PayeeCollection: Retry
    
    DateCollection --> ModeCollection: Date Collected
    DateCollection --> DateRetry: Unclear Response
    
    DateRetry --> DateCollection: Retry
    ModeCollection --> ExecutiveDetails: Field Executive Mode
    ModeCollection --> ReasonCollection: Other Modes
    ModeCollection --> ModeRetry: Unclear Response
    
    ModeRetry --> ModeCollection: Retry
    ExecutiveDetails --> ReasonCollection: Details Collected
    
    ReasonCollection --> AmountCollection: Reason Collected
    ReasonCollection --> ReasonRetry: Unclear Response
    
    ReasonRetry --> ReasonCollection: Retry
    AmountCollection --> SummaryGeneration: Amount Collected
    AmountCollection --> AmountRetry: Unclear Response
    
    AmountRetry --> AmountCollection: Retry
    SummaryGeneration --> SummaryPresentation: Summary Ready
    
    SummaryPresentation --> ConfirmationWait: Present to User
    ConfirmationWait --> EndSuccess: Confirmed
    ConfirmationWait --> EditInformation: Edit Requested
    ConfirmationWait --> ConfirmationRetry: Unclear Response
    
    EditInformation --> SummaryGeneration: Information Updated
    ConfirmationRetry --> ConfirmationWait: Retry
    
    EndSuccess --> [*]
    EndWrongPerson --> [*]
    EndNoLoan --> [*]
    EndNoPayment --> [*]
    EndMaxRetries --> [*]
```

## 4. Question Flow Logic

```mermaid
flowchart TD
    START([Start Question Flow]) --> Q1{Q1: Identity Confirmation}
    
    Q1 -->|Confirmed| Q2{Q2: Availability Check}
    Q1 -->|Wrong Person| CHECK_AVAIL[Check When Available]
    Q1 -->|Unclear| RETRY_Q1[Retry Q1]
    
    CHECK_AVAIL --> END_WRONG[End: Wrong Person]
    RETRY_Q1 --> Q1
    
    Q2 -->|Available| Q3{Q3: Loan Taken}
    Q2 -->|Not Available| END_UNAVAIL[End: Not Available]
    Q2 -->|Unclear| RETRY_Q2[Retry Q2]
    
    RETRY_Q2 --> Q2
    
    Q3 -->|Yes| Q4{Q4: EMI Payment}
    Q3 -->|No| END_NO_LOAN[End: No Loan]
    Q3 -->|Unclear| RETRY_Q3[Retry Q3]
    
    RETRY_Q3 --> Q3
    
    Q4 -->|Yes| Q5{Q5: Payee}
    Q4 -->|No| END_NO_PAYMENT[End: No Payment]
    Q4 -->|Unclear| RETRY_Q4[Retry Q4]
    
    RETRY_Q4 --> Q4
    
    Q5 -->|Self| Q7{Q7: Payment Date}
    Q5 -->|Family/Friend/Third Party| Q6{Q6: Payee Details}
    Q5 -->|Unclear| RETRY_Q5[Retry Q5]
    
    RETRY_Q5 --> Q5
    Q6 --> Q7
    
    Q7 -->|Date Provided| Q8{Q8: Payment Mode}
    Q7 -->|Unclear| RETRY_Q7[Retry Q7]
    
    RETRY_Q7 --> Q7
    
    Q8 -->|Online/UPI/NEFT/RTGS| Q10{Q10: Payment Reason}
    Q8 -->|Field Executive/Cash| Q9{Q9: Executive Details}
    Q8 -->|Branch/Outlet/NACH| Q10
    Q8 -->|Unclear| RETRY_Q8[Retry Q8]
    
    RETRY_Q8 --> Q8
    Q9 --> Q10
    
    Q10 -->|Reason Provided| Q11{Q11: Amount}
    Q10 -->|Unclear| RETRY_Q10[Retry Q10]
    
    RETRY_Q10 --> Q10
    
    Q11 -->|Amount Provided| SUMMARY[Generate Summary]
    Q11 -->|Unclear| RETRY_Q11[Retry Q11]
    
    RETRY_Q11 --> Q11
    
    SUMMARY --> CONFIRM{User Confirmation}
    CONFIRM -->|Confirmed| CLOSING[Closing Statement]
    CONFIRM -->|Edit Required| EDIT[Edit Information]
    CONFIRM -->|Unclear| RETRY_CONFIRM[Retry Confirmation]
    
    EDIT --> SUMMARY
    RETRY_CONFIRM --> CONFIRM
    CLOSING --> END_SUCCESS[End: Success]
    
    %% Retry Limits
    RETRY_Q1 -.->|Max Retries| END_MAX_RETRY[End: Max Retries]
    RETRY_Q2 -.->|Max Retries| END_MAX_RETRY
    RETRY_Q3 -.->|Max Retries| END_MAX_RETRY
    RETRY_Q4 -.->|Max Retries| END_MAX_RETRY
    RETRY_Q5 -.->|Max Retries| END_MAX_RETRY
    RETRY_Q7 -.->|Max Retries| END_MAX_RETRY
    RETRY_Q8 -.->|Max Retries| END_MAX_RETRY
    RETRY_Q10 -.->|Max Retries| END_MAX_RETRY
    RETRY_Q11 -.->|Max Retries| END_MAX_RETRY
    RETRY_CONFIRM -.->|Max Retries| END_MAX_RETRY

    %% Styling
    classDef questionNode fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef retryNode fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef endNode fill:#c8e6c9,stroke:#388e3c,stroke-width:2px
    classDef errorNode fill:#ffcdd2,stroke:#d32f2f,stroke-width:2px

    class Q1,Q2,Q3,Q4,Q5,Q6,Q7,Q8,Q9,Q10,Q11,CONFIRM questionNode
    class RETRY_Q1,RETRY_Q2,RETRY_Q3,RETRY_Q4,RETRY_Q5,RETRY_Q7,RETRY_Q8,RETRY_Q10,RETRY_Q11,RETRY_CONFIRM retryNode
    class END_SUCCESS,END_WRONG,END_UNAVAIL,END_NO_LOAN,END_NO_PAYMENT endNode
    class END_MAX_RETRY errorNode
```

## 5. Data Extraction and Processing Flow

```mermaid
flowchart LR
    subgraph "Input Processing"
        AUDIO_IN[Audio Input] --> ASR[Speech Recognition]
        ASR --> TEXT[Transcribed Text]
    end
    
    subgraph "Context Building"
        TEXT --> CONTEXT[Build Context]
        SESSION_DATA[Session Data] --> CONTEXT
        CONVERSATION_HISTORY[Conversation History] --> CONTEXT
    end
    
    subgraph "LLM Processing"
        CONTEXT --> LLM[Gemini LLM]
        LLM --> RESPONSE[Structured Response]
    end
    
    subgraph "Data Extraction"
        RESPONSE --> EXTRACT[Extract Information]
        EXTRACT --> IDENTITY[Identity Confirmed]
        EXTRACT --> LOAN[Loan Status]
        EXTRACT --> PAYMENT[Payment Status]
        EXTRACT --> PAYEE[Payee Information]
        EXTRACT --> DATE[Payment Date]
        EXTRACT --> MODE[Payment Mode]
        EXTRACT --> REASON[Payment Reason]
        EXTRACT --> AMOUNT[Payment Amount]
    end
    
    subgraph "Session Update"
        IDENTITY --> UPDATE[Update Session]
        LOAN --> UPDATE
        PAYMENT --> UPDATE
        PAYEE --> UPDATE
        DATE --> UPDATE
        MODE --> UPDATE
        REASON --> UPDATE
        AMOUNT --> UPDATE
    end
    
    subgraph "Response Generation"
        UPDATE --> CHECK_COMPLETE{All Data Collected?}
        CHECK_COMPLETE -->|No| NEXT_Q[Generate Next Question]
        CHECK_COMPLETE -->|Yes| SUMMARY[Generate Summary]
        NEXT_Q --> TTS[Text-to-Speech]
        SUMMARY --> TTS
    end
    
    subgraph "Output"
        TTS --> AUDIO_OUT[Audio Output]
        SUMMARY --> JSON_OUT[JSON Response]
    end

    %% Styling
    classDef inputNode fill:#e8f5e8,stroke:#4caf50,stroke-width:2px
    classDef processingNode fill:#e3f2fd,stroke:#2196f3,stroke-width:2px
    classDef dataNode fill:#fff3e0,stroke:#ff9800,stroke-width:2px
    classDef outputNode fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px

    class AUDIO_IN,TEXT inputNode
    class CONTEXT,LLM,RESPONSE,EXTRACT,UPDATE,CHECK_COMPLETE,NEXT_Q processingNode
    class IDENTITY,LOAN,PAYMENT,PAYEE,DATE,MODE,REASON,AMOUNT,SESSION_DATA,CONVERSATION_HISTORY dataNode
    class AUDIO_OUT,JSON_OUT,TTS,SUMMARY outputNode
```

## 6. Error Handling and Fallback Flow

```mermaid
flowchart TD
    PROCESS[Normal Processing] --> ERROR_CHECK{Error Occurred?}
    
    ERROR_CHECK -->|No| SUCCESS[Continue Normal Flow]
    ERROR_CHECK -->|Yes| ERROR_TYPE{Error Type?}
    
    ERROR_TYPE -->|Audio Error| AUDIO_ERROR[Audio Processing Error]
    ERROR_TYPE -->|ASR Error| ASR_ERROR[Speech Recognition Error]
    ERROR_TYPE -->|LLM Error| LLM_ERROR[LLM Processing Error]
    ERROR_TYPE -->|TTS Error| TTS_ERROR[Text-to-Speech Error]
    ERROR_TYPE -->|Network Error| NETWORK_ERROR[Network Connection Error]
    ERROR_TYPE -->|Database Error| DB_ERROR[Database Error]
    
    AUDIO_ERROR --> AUDIO_FALLBACK[Use Fallback Audio Processing]
    ASR_ERROR --> ASR_FALLBACK[Request User to Repeat]
    LLM_ERROR --> LLM_FALLBACK[Use Predefined Response]
    TTS_ERROR --> TTS_FALLBACK[Use Alternative TTS]
    NETWORK_ERROR --> NETWORK_FALLBACK[Retry with Backoff]
    DB_ERROR --> DB_FALLBACK[Use Session Cache]
    
    AUDIO_FALLBACK --> RETRY_COUNT{Retry Count < Max?}
    ASR_FALLBACK --> RETRY_COUNT
    LLM_FALLBACK --> RETRY_COUNT
    TTS_FALLBACK --> RETRY_COUNT
    NETWORK_FALLBACK --> RETRY_COUNT
    DB_FALLBACK --> RETRY_COUNT
    
    RETRY_COUNT -->|Yes| INCREMENT[Increment Retry Count]
    RETRY_COUNT -->|No| GRACEFUL_DEGRADATION[Graceful Degradation]
    
    INCREMENT --> PROCESS
    GRACEFUL_DEGRADATION --> END_SESSION[End Session with Apology]
    
    SUCCESS --> CONTINUE[Continue Processing]

    %% Styling
    classDef normalNode fill:#c8e6c9,stroke:#4caf50,stroke-width:2px
    classDef errorNode fill:#ffcdd2,stroke:#f44336,stroke-width:2px
    classDef fallbackNode fill:#fff9c4,stroke:#ff9800,stroke-width:2px
    classDef decisionNode fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px

    class PROCESS,SUCCESS,CONTINUE normalNode
    class AUDIO_ERROR,ASR_ERROR,LLM_ERROR,TTS_ERROR,NETWORK_ERROR,DB_ERROR,END_SESSION errorNode
    class AUDIO_FALLBACK,ASR_FALLBACK,LLM_FALLBACK,TTS_FALLBACK,NETWORK_FALLBACK,DB_FALLBACK,GRACEFUL_DEGRADATION fallbackNode
    class ERROR_CHECK,ERROR_TYPE,RETRY_COUNT decisionNode
```

## 7. Performance Monitoring Flow

```mermaid
sequenceDiagram
    participant User as 👤 User
    participant System as 🖥️ System
    participant Monitor as 📊 Monitor
    participant Logger as 📝 Logger
    participant Metrics as 📈 Metrics

    User->>System: Start Interaction
    System->>Monitor: Start Tracking
    Monitor->>Logger: Log Start Event
    
    System->>System: Process VAD
    System->>Monitor: Record VAD Latency
    
    System->>System: Process ASR
    System->>Monitor: Record ASR Latency
    
    System->>System: Process LLM
    System->>Monitor: Record LLM Latency
    
    System->>System: Process TTS
    System->>Monitor: Record TTS Latency
    
    System->>User: Deliver Response
    System->>Monitor: Record Total Latency
    
    Monitor->>Metrics: Update Performance Metrics
    Monitor->>Logger: Log Performance Data
    
    alt Performance Issue Detected
        Monitor->>System: Trigger Alert
        System->>Logger: Log Performance Issue
    end
    
    Note over Monitor,Metrics: Continuous monitoring throughout session
```

## Key Performance Indicators (KPIs)

### Latency Metrics
- **VAD Processing**: < 50ms per frame
- **ASR Processing**: < 2 seconds per utterance
- **LLM Processing**: < 3 seconds per request
- **TTS Processing**: < 1 second for first chunk
- **End-to-End**: < 5 seconds total response time

### Quality Metrics
- **ASR Accuracy**: > 95% for clear speech
- **Intent Recognition**: > 90% accuracy
- **Conversation Completion**: > 85% success rate
- **User Satisfaction**: Based on successful data collection

### System Metrics
- **WebSocket Connection**: 99.9% uptime
- **Database Response**: < 100ms average
- **Error Rate**: < 1% of total interactions
- **Concurrent Users**: Support for 100+ simultaneous sessions