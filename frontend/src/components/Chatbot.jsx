import React, { useState, useRef, useEffect } from 'react'
import { createSession, submitAnswer, getSummary, confirmSummary, getCustomers } from '../services/api'
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket'

const Chatbot = () => {
  const [messages, setMessages] = useState([
    {
      type: 'bot',
      text: 'Welcome! Please select a customer to start the survey.',
      timestamp: new Date(),
    },
  ])
  const [sessionId, setSessionId] = useState(null)
  const [customers, setCustomers] = useState([])
  const [selectedCustomer, setSelectedCustomer] = useState(null)
  const [customerName, setCustomerName] = useState('')
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingCustomers, setIsLoadingCustomers] = useState(true)
  const [surveyState, setSurveyState] = useState('customer_selection') // 'customer_selection', 'name', 'survey', 'summary', 'confirmation', 'confirmed'
  const [summary, setSummary] = useState(null)
  const [confirmationRetries, setConfirmationRetries] = useState(0)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Voice WebSocket hook for outbound calls
  const {
    isConnected,
    connectionStatus,
    isStreaming,
    isPlayingTTS,
    currentTranscript,
    transcripts,
    connect,
    disconnect,
    clearTranscripts,
  } = useVoiceWebSocket()

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    // Fetch customers on mount
    const fetchCustomers = async () => {
      try {
        setIsLoadingCustomers(true)
        const response = await getCustomers()
        setCustomers(response.customers || [])
      } catch (error) {
        addMessage('bot', `Error loading customers: ${error.message}`)
      } finally {
        setIsLoadingCustomers(false)
      }
    }
    fetchCustomers()
  }, [])

  useEffect(() => {
    if (surveyState === 'survey' || surveyState === 'name' || surveyState === 'confirmation') {
      inputRef.current?.focus()
    }
  }, [surveyState])

  const addMessage = (type, text) => {
    setMessages((prev) => [
      ...prev,
      {
        type,
        text,
        timestamp: new Date(),
      },
    ])
  }

  const handleCustomerSelect = async (customer) => {
    console.log("📞 Customer selected:", customer)
    setSelectedCustomer(customer)
    setCustomerName(customer.customer_name)

    // Trigger the outbound call with selected customer
    setIsLoading(true)
    try {
      // Create session via API
      console.log("📝 Creating session for:", customer.customer_name)
      const response = await createSession(customer.customer_name)
      console.log("✅ Session created:", response.session_id)
      setSessionId(response.session_id)

      // Connect WebSocket and start voice call
      console.log("🔗 Connecting WebSocket with session:", response.session_id)
      await connect("traditional", response.session_id, customer.customer_name)
      console.log("✅ Connect call completed")

      setSurveyState('survey')
      addMessage('user', `Calling: ${customer.customer_name}`)
      // Connection status will be updated via useVoiceWebSocket hook
    } catch (error) {
      console.error("❌ Error in handleCustomerSelect:", error)
      addMessage('bot', `Error starting call: ${error.message}`)
      setSelectedCustomer(null)
      setCustomerName('')
    } finally {
      setIsLoading(false)
    }
  }

  const handleStartSurvey = async () => {
    if (!customerName.trim()) {
      addMessage('bot', 'Please enter your name to continue.')
      return
    }

    setIsLoading(true)
    try {
      const response = await createSession(customerName.trim())
      setSessionId(response.session_id)
      setSurveyState('survey')
      addMessage('user', `My name is ${customerName.trim()}`)
      if (response.question) {
        addMessage('bot', response.question)
      }
    } catch (error) {
      addMessage('bot', `Error: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmitAnswer = async () => {
    if (!inputValue.trim() || !sessionId) return

    const answer = inputValue.trim()
    setInputValue('')
    addMessage('user', answer)
    setIsLoading(true)

    try {
      const response = await submitAnswer(sessionId, answer)

      if (response.status === 'COMPLETED') {
        // If skip_summary is true (wrong number case), go directly to closing statement
        if (response.skip_summary) {
          setSurveyState('confirmed')
          try {
            const confirmResponse = await confirmSummary(sessionId)
            addMessage('bot', confirmResponse.closing_statement)
          } catch (error) {
            addMessage('bot', 'Dhanyawad aapke samay ke liye. Aapka din shubh ho!')
          }
        } else {
          setSurveyState('summary')
          await fetchSummary()
        }
      } else if (response.status === 'END') {
        addMessage('bot', response.message || 'Session ended due to maximum retries.')
        setSurveyState('name')
      } else if (response.status === 'REPEAT') {
        if (response.message && response.question) {
          // Combine message and question into one message
          addMessage('bot', `${response.message} ${response.question}`)
        } else if (response.message) {
          addMessage('bot', response.message)
        } else if (response.question) {
          addMessage('bot', response.question)
        }
      } else if (response.status === 'NEXT') {
        if (response.question) {
          addMessage('bot', response.question)
        }
      }
    } catch (error) {
      addMessage('bot', `Error: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const fetchSummary = async () => {
    if (!sessionId) return

    setIsLoading(true)
    try {
      const response = await getSummary(sessionId)
      setSummary(response.summary)
      // Combine summary and confirmation question into one message
      addMessage('bot', `${response.summary}\n\nKya ye jankari sahi hai?`)
      setSurveyState('confirmation') // Change state to wait for confirmation
      setConfirmationRetries(0) // Reset retry counter
    } catch (error) {
      addMessage('bot', `Error: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleConfirmationAnswer = async () => {
    if (!inputValue.trim() || !sessionId) return

    const answer = inputValue.trim().toLowerCase()
    addMessage('user', inputValue.trim())
    setInputValue('')
    setIsLoading(true)

    try {
      // More robust confirmation detection - check for yes patterns
      const yesPatterns = [
        'yes', 'haan', 'ha', 'sahi', 'bilkul', 'theek', 'ok', 'okay', 'y', 'h',
        'haa', 'haaa', 'haaaa', 'sahi hai', 'sahi h', 'haa sahi', 'haa sahi h',
        'haa shai', 'haa shai h', 'theek hai', 'bilkul sahi', 'sahi hai ji',
        'haan sahi', 'haan sahi hai', 'haan sahi h', 'haan shai', 'haan shai h',
        'ji haan', 'ji haa', 'haan ji', 'haa ji'
      ]

      // Check if answer contains any yes pattern
      const confirmed = yesPatterns.some(pattern => {
        // Exact match
        if (answer === pattern) return true
        // Contains pattern (for phrases like "haa sahi h")
        if (answer.includes(pattern) && pattern.length > 2) return true
        // Starts with pattern (for "haa", "haan", etc.)
        if (answer.startsWith(pattern) && pattern.length >= 2) return true
        return false
      })

      if (confirmed) {
        const response = await confirmSummary(sessionId)
        setSurveyState('confirmed')
        setConfirmationRetries(0)
        addMessage('bot', response.closing_statement)
      } else {
        // If not confirmed, ask again (max 2 retries)
        if (confirmationRetries < 2) {
          setConfirmationRetries(prev => prev + 1)
          addMessage('bot', 'Kripya confirm karein, kya ye jankari sahi hai?')
        } else {
          // After max retries, assume confirmed and proceed
          const response = await confirmSummary(sessionId)
          setSurveyState('confirmed')
          setConfirmationRetries(0)
          addMessage('bot', response.closing_statement)
        }
      }
    } catch (error) {
      addMessage('bot', `Error: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (surveyState === 'name') {
        handleStartSurvey()
      } else if (surveyState === 'survey') {
        handleSubmitAnswer()
      } else if (surveyState === 'confirmation') {
        handleConfirmationAnswer()
      }
    }
  }

  const handleRestart = () => {
    // Disconnect WebSocket if connected
    if (isConnected) {
      disconnect()
    }
    clearTranscripts()

    setMessages([
      {
        type: 'bot',
        text: 'Welcome! Please select a customer to start the survey.',
        timestamp: new Date(),
      },
    ])
    setSessionId(null)
    setSelectedCustomer(null)
    setCustomerName('')
    setInputValue('')
    setSurveyState('customer_selection')
    setSummary(null)
    setConfirmationRetries(0)
  }

  // Update messages when transcripts change from WebSocket
  useEffect(() => {
    if (!transcripts || transcripts.length === 0) {
      return;
    }

    // Process all transcripts to ensure none are missed
    setMessages((prevMessages) => {
      const updatedMessages = [...prevMessages];
      let hasChanges = false;

      transcripts.forEach((transcript) => {
        // Process user transcript (ASR)
        if (transcript.asrText && transcript.asrText.trim() !== "") {
          const existingUserMsg = updatedMessages.find(
            (m) => m.type === "user" && m.text === transcript.asrText
          );
          if (!existingUserMsg) {
            updatedMessages.push({
              type: "user",
              text: transcript.asrText,
              timestamp: new Date(transcript.timestamp || Date.now()),
            });
            hasChanges = true;
            console.log("✅ Added user message from transcript:", transcript.asrText);
          }
        }

        // Process bot response
        if (transcript.chatbotResponse && transcript.chatbotResponse.trim() !== "") {
          const existingBotMsg = updatedMessages.find(
            (m) => m.type === "bot" && m.text === transcript.chatbotResponse
          );
          if (!existingBotMsg) {
            updatedMessages.push({
              type: "bot",
              text: transcript.chatbotResponse,
              timestamp: new Date(transcript.timestamp || Date.now()),
            });
            hasChanges = true;
            console.log("✅ Added bot message from transcript:", transcript.chatbotResponse);
          }
        }
      });

      return hasChanges ? updatedMessages : prevMessages;
    });
  }, [transcripts])

  // Clear loading state when call starts
  useEffect(() => {
    if (isConnected && connectionStatus && connectionStatus.includes('starting')) {
      setIsLoading(false)
    }
  }, [isConnected, connectionStatus])

  return (
    <div className="flex items-center justify-center min-h-screen p-4">
      <div className="w-full max-w-4xl bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col h-[90vh]">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white p-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">L&T Finance Customer Survey</h1>
              <p className="text-blue-100 text-sm mt-1">
                Please provide your information to help us serve you better
              </p>
            </div>
            {isConnected && (
              <div className="flex items-center space-x-2">
                <div className={`w-3 h-3 rounded-full ${isStreaming ? 'bg-green-400 animate-pulse' : 'bg-gray-400'}`}></div>
                <span className="text-sm">
                  {isPlayingTTS ? '🔊 Playing...' : isStreaming ? '🎤 Listening...' : connectionStatus}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-gray-50">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'
                }`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${message.type === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-800 shadow-md border border-gray-200'
                  }`}
              >
                <p className="whitespace-pre-wrap break-words">{message.text}</p>
                <span
                  className={`text-xs mt-1 block ${message.type === 'user' ? 'text-blue-100' : 'text-gray-500'
                    }`}
                >
                  {message.timestamp.toLocaleTimeString()}
                </span>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-white rounded-2xl px-4 py-3 shadow-md border border-gray-200">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-200 p-4 bg-white">
          {surveyState === 'customer_selection' && (
            <div className="space-y-4">
              {isLoadingCustomers ? (
                <div className="text-center py-4">
                  <div className="inline-flex items-center space-x-2 text-gray-600">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                    <span className="ml-2">Loading customers...</span>
                  </div>
                </div>
              ) : customers.length > 0 ? (
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  <p className="text-sm font-semibold text-gray-700 mb-2">Select a customer to start the call:</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {customers.map((customer) => (
                      <button
                        key={customer.id}
                        onClick={() => handleCustomerSelect(customer)}
                        disabled={isLoading}
                        className="px-4 py-3 bg-white border-2 border-gray-300 rounded-lg text-left hover:border-blue-500 hover:bg-blue-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <div className="font-semibold text-gray-800">{customer.customer_name}</div>
                        {customer.contact_number && (
                          <div className="text-sm text-gray-500 mt-1">{customer.contact_number}</div>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-center py-4 text-gray-500">
                  No customers found. Please try again later.
                </div>
              )}
            </div>
          )}

          {surveyState === 'name' && (
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Enter your name..."
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={isLoading}
              />
              <button
                onClick={handleStartSurvey}
                disabled={isLoading || !customerName.trim()}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Start Survey
              </button>
            </div>
          )}

          {surveyState === 'survey' && (
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your answer..."
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={isLoading}
              />
              <button
                onClick={handleSubmitAnswer}
                disabled={isLoading || !inputValue.trim()}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Send
              </button>
            </div>
          )}

          {surveyState === 'confirmation' && (
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Haan / Yes..."
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={isLoading}
              />
              <button
                onClick={handleConfirmationAnswer}
                disabled={isLoading || !inputValue.trim()}
                className="px-6 py-3 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Send
              </button>
            </div>
          )}

          {surveyState === 'confirmed' && (
            <div className="flex justify-center">
              <button
                onClick={handleRestart}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition-colors"
              >
                Start New Survey
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Chatbot


