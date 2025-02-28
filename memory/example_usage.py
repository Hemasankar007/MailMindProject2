import os
import json
from memory_integration import MemoryIntegration  # This should work now

# Example email data
example_email = {
    "id": "msg123",
    "threadId": "thread456",
    "payload": {
        "headers": [
            {"name": "From", "value": "John Smith <john.smith@example.com>"},
            {"name": "To", "value": "sofia@yourdomain.com"},
            {"name": "Subject", "value": "Project Phoenix Update"}
        ]
    },
    "snippet": "Hi Sofia, I wanted to give you an update on Project Phoenix. We've made significant progress with the implementation phase. The team at Acme Corp is very pleased with our work so far. Could we schedule a meeting next week to discuss the next steps? Best regards, John"
}

# Initialize memory integration
memory = MemoryIntegration()

# Process the example email
context = memory.process_email(example_email)

print("Thread Context:")
print(context['thread_context'])

print("\nTopics:")
print(context['topics'])

print("\nEntities:")
for entity in context['entities']:
    print(f"- {entity['name']} ({entity['type']})")

# Example of generating a response with memory context
print("\nExample of how to use memory context in response generation:")
print("=" * 50)
print("When generating a response, include the memory context in the prompt:")
print("=" * 50)
print(f"""
You are Sofia, an AI assistant. You're responding to an email from a user.
Use the following conversation context and entity information to personalize your response:

{memory.get_memory_context('thread456')}

Write a complete, helpful response as Sofia:
""")