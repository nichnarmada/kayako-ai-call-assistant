# **Kayako AI Call Assistant – Product Requirements**

## **Understand the Problem**

We want to create a system where:

1. Kayako can automatically answer incoming customer calls using AI.
2. The system retrieves answers from a connected knowledge base.
3. If an answer is found, the AI responds in real-time on the call.
4. If an answer is not found, the AI ends the call by informing the caller that an expert will follow up.
5. A ticket is created in Kayako with the full call context, including key details like email and call transcript.

---

## **Key Components Needed**

1. **Voice AI System**
   - Ability to answer and process incoming calls.
   - Human-like speech synthesis and natural language understanding (NLU).
2. **Knowledge Base Integration**
   - AI retrieves relevant responses from the knowledge base via API.
3. **Call Handling Logic**
   - Determines whether an answer is found.
   - Ends call if no answer is available and triggers expert follow-up.
4. **Kayako API Integration**
   - Creates a ticket with call details, including transcript and caller information.
5. **User Data Capture**
   - Collects key details such as caller’s email and reason for calling.

---

## **User Flow Overview**

1. A customer calls the support line.
2. Kayako AI answers the call using human-like speech.
3. The AI extracts key details (e.g., email, issue description).
4. It searches the knowledge base for a relevant answer.
   - If an answer is found → AI delivers the response in real-time.
   - If no answer is found → AI informs the caller that a human agent will follow up.
5. The system ends the call and automatically creates a Kayako support ticket.
6. A human agent reviews the ticket and follows up as needed.

---

## **Example User Experience**

1. **Customer Calls Support**
   - AI: _"Thank you for calling Kayako Support. How can I assist you today?"_
2. **AI Identifies the Issue & Searches Knowledge Base**
   - Customer: _"I forgot my password. How do I reset it?"_
   - AI (searches KB, finds answer): _"You can reset your password by visiting our login page and clicking 'Forgot Password.' Would you like me to send you a reset link?"_
3. **No Answer Found Scenario**
   - Customer: _"I need help with a custom API integration."_
   - AI (no KB match): _"I’ll pass this on to our expert support team. They’ll follow up shortly. Have a great day\!"_
4. **Ticket Created in Kayako**
   - A new ticket logs the call transcript, caller details, and AI actions.

---

## **Architectural Building Blocks**

1. **Voice AI Engine**
   - Speech-to-text (STT) for understanding customer input.
   - Text-to-speech (TTS) for natural, human-like responses.
2. **Knowledge Base Search Module**
   - Connects to Kayako's KB via API.
   - Retrieves relevant articles and provides summarized answers.
3. **Call Management System**
   - Handles incoming calls.
   - Determines if an answer exists.
   - Ends call appropriately.
4. **Ticket Creation in Kayako**
   - Logs call details, transcript, and key extracted information.
   - Tags tickets for agent review.

---

## **Benefits & Takeaways**

1. **Faster response times** – AI handles common questions instantly.
2. **Reduced agent workload** – AI resolves simple issues, leaving complex cases for experts.
3. **Seamless customer experience** – AI speaks naturally and provides immediate answers.
4. **Automatic ticketing** – Ensures no customer request is lost.

---

### **User Stories & Acceptance Criteria**

### **User Story 1: AI Handles Incoming Calls & Provides Answers**

**Title:** As a VP of Customer Support, I want AI to handle incoming support calls so my team can focus on more complex issues.

**Description:** The AI assistant should answer calls, understand customer inquiries, and provide accurate responses using our knowledge base.

**Acceptance Criteria:**

- AI system automatically answers incoming customer calls.
- AI listens to customer inquiries and processes them using natural language understanding.
- AI searches the knowledge base and provides relevant answers in a natural, conversational tone.
- AI handles simple conversational flows, such as clarifying questions when needed.

---

### **User Story 2: AI Escalates Unresolved Issues to Human Agents**

**Title:** As a VP of Customer Support, I want AI to recognize when it doesn’t have an answer and ensure a human follows up, so no customer inquiry is left unresolved.

**Description:** If the AI cannot find an answer in the knowledge base, it should politely end the call while assuring the customer that a human agent will follow up.

**Acceptance Criteria:**

- AI searches the knowledge base for answers before responding.
- If no relevant answer is found, AI informs the caller that a human agent will follow up.
- AI ends the call professionally and ensures a support ticket is created.

---

### **User Story 3: AI Captures Key Customer Information**

**Title:** As a VP of Customer Support, I want AI to capture key customer details so my team has all the necessary context to follow up efficiently.

**Description:** AI should collect and log important customer details such as name, email, and issue summary to ensure accurate and efficient follow-ups.

**Acceptance Criteria:**

- AI asks for and confirms the customer’s email address.
- AI summarizes the customer’s issue based on the conversation.
- AI logs the collected information into a new support ticket in Kayako.

---

### **User Story 4: AI Automatically Creates Support Tickets**

**Title:** As a VP of Customer Support, I want AI to automatically generate tickets from calls so my team can easily track and manage customer inquiries.

**Description:** The AI should create a support ticket in Kayako with the full call transcript, customer details, and issue summary.

**Acceptance Criteria:**

- AI generates a ticket when a call ends.
- Ticket includes the full call transcript, caller details, and a summary of the issue.
- Ticket is categorized and tagged appropriately for easy triage by the support team.

---

### **User Story 5: AI Integrates Seamlessly with Kayako’s APIs**

**Title:** As a VP of Customer Support, I want AI to connect with Kayako’s APIs so it can retrieve knowledge base answers and create tickets without manual intervention.

**Description:** The AI assistant should use Kayako’s APIs to pull information from the knowledge base and log support tickets.

**Acceptance Criteria:**

- AI retrieves knowledge base articles via the Kayako API.
- AI creates and updates support tickets using the Kayako API.
- API calls follow security and authentication best practices.

---

## **Developer Resources**

**Operational:**

1. **Daily demos are at 11am CST**. Everyone on this email is on the invite. If you know of any other Gauntlet Dev that's working on this project please add them to the Google Calendar invite.
2. [Here is the link](https://jigtree-gsd.slack.com/archives/C08DG8EDSNR) to our official slack channel.
3. Here are the [project requirements](https://docs.google.com/document/d/1WcZ_wy_pQhCAFSYHSd-rtRQRjDbz20DEXhZSMA0uq-o/edit?usp=sharing).
4. Here are the [Kayako API docs](https://developer.kayako.com/api/v1/reference/introduction/).
5. Here are the credentials to a test instance you all can use to troubleshoot/test.
   1. [https://doug-test.kayako.com/agent/](https://doug-test.kayako.com/agent/)
   2. [anna.kim@trilogy.com](mailto:anna.kim@trilogy.com)
   3. Kayakokayako1?

**FAQ’s:**

1. **Q: Do you have a test instance I can use?**
   1. **A:** Yes, credentials below:
      1. [https://doug-test.kayako.com/agent/](https://doug-test.kayako.com/agent/)
      2. [anna.kim@trilogy.com](mailto:anna.kim@trilogy.com)
      3. Kayakokayako1?
2. **Q: Is the agent required to operate on regular phone calls or is there going to be a web-only communication? This is directly impacting overall project design due to another layer of complexity introduced by a platform like Twilio.**
   1. **A:** The agent is required to operate on regular phone calls. Looks like Twilio has a free 7 day version. If an expense is required, let me know what package you need and I'll set it up and send you all credentials.
3. **Q: \- Your pricing page defines an existing AI calling agent feature. Can you kindly elaborate on: a) The existing offering b) Biggest pain points you have with the current solution? e) Would it be possible to get on a call to do a live demo?**
   1. **A: Overview of Kayako:**
      1. Kayako is our customer service platform that continues to evolve with AI-powered features. Our recent developments focus on automating repetitive tasks and improving agent efficiency. Our key features include AI-suggested responses based on knowledge base content, self-learning capabilities from closed tickets, conversation summarization, and an AI ticket assistant for information retrieval. We're also planning to introduce audio transcription and context-aware autocomplete features.
   2. **Pain Points and Solutions:**
      1. **Response Generation Pain Point:** Our agents waste significant time crafting responses from scratch for each ticket, leading to inconsistent answers and slower response times. Some agents write detailed responses while others keep them brief, creating an inconsistent customer experience.
         1. **Solution:** Our AI-suggested responses now automatically generate contextual responses using our knowledge base, enabling agents to send or edit pre-crafted responses rather than starting from zero.
      2. **Knowledge Management Pain Point:** Our team constantly repeats answers to similar questions because we lack efficient knowledge sharing. When an agent solves a complex issue, that solution often isn't captured for future use, forcing others to solve the same problem again.
         1. **Solution:** Our self-learning mode now automatically learns from successfully closed tickets, building a growing knowledge base that suggests proven solutions for similar future inquiries.
      3. **Ticket Navigation Pain Point:** Our agents spend excessive time scrolling through long ticket threads to understand context, often missing important details buried in lengthy conversations. This slows down resolution times and frustrates both agents and customers.
         1. **Solution:** Our one-click AI summary feature instantly condenses entire ticket conversations, while our AI Ticket Assistant lets agents chat directly with tickets to find specific information quickly.
      4. **Media Handling Pain Point:** When customers send audio messages, our agents must manually transcribe them \- a tedious process that takes valuable time and makes searching through past audio content nearly impossible.
         1. **Solution:** Our upcoming AI audio transcription will automatically convert audio to searchable text and provide summaries, eliminating manual transcription work.
      5. **Response Composition Pain Point:** Our agents spend too much time composing responses, often retyping similar phrases and struggling to maintain context across long ticket threads.
         1. **Solution:** Our planned AI autocomplete will speed up response time by suggesting completions based on both typing patterns and ticket context, reducing composition time while maintaining accuracy.
4. **Q: Would it be possible to get on a call to do a live demo?**
   1. **A:** Yes, however [here are demo videos](https://drive.google.com/drive/folders/1XMPKMWAzCSQcgSjU5iHWNsc28j2Me1rh?usp=sharing) of all of our AI features for you all to view easier.
5. **Q: Can Kayako’s API retrieve issues by a customer phone number?**
   1. **A:** Kayako's API does provide the capability to retrieve information based on various user attributes, including phone numbers. To retrieve issues by a customer's phone number, you would typically use the API endpoint for listing conversations or cases, and apply a filter to search for the specific phone number associated with a user's account.
   2. Here's a general approach to how you might do this:
      1. Use the endpoint to retrieve user information based on the phone number. This might involve searching through user accounts to find the one associated with the given phone number.
      2. Once you have the user's ID, use the endpoint for retrieving cases or conversations associated with that user ID.
   3. Please note that the exact API endpoint and method to use will depend on the specific details of your implementation and the permissions set within your Kayako instance. You may need to review the API documentation to find the appropriate endpoint and understand the required parameters for your query.
6. **Q: Would your team be open to a solution that sends texts? Example use case: If we need to gather an email address from a user quickly**
   1. **A:** Yes, but focus on initial use cases first.
7. Q. Suggestions for improvement to the agent. Are these useful?

   a. Semantic and context analysis of customer calls/audio responses to tag good AI responses and bad AI responses.

   c. AI agent has memory so it remembers past customer interactions and preferences and uses those in future interactions.

   1. e. a higher order Question Answer interface, Where human agents can override certain answers if the KB is not up to date, or add additional question answers that might not be in the KB.
