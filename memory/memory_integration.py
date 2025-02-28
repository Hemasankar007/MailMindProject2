import os
import re
import time
from typing import Dict, List, Optional, Any
from memory.conversation_store import ConversationMemoryStore

class MemoryIntegration:
    """Integrates the conversation memory store with the Gmail agent"""
    
    def __init__(self, storage_path: str = None):
        """Initialize the memory integration"""
        self.memory = ConversationMemoryStore(storage_path)
    
    def process_email(self, email_data: Dict[str, Any], is_from_agent: bool = False) -> Dict[str, Any]:
        """Process an email and update the memory store
        
        Args:
            email_data: Dictionary containing email information from Gmail API
            is_from_agent: Whether this email is from the agent
            
        Returns:
            Dictionary with memory context for generating responses
        """
        # Extract email information
        message_id = email_data.get('id', '')
        thread_id = email_data.get('threadId', '')
        headers = email_data.get('payload', {}).get('headers', [])
        
        # Extract headers
        sender = ''
        recipients = []
        subject = ''
        
        for header in headers:
            name = header.get('name', '').lower()
            value = header.get('value', '')
            
            if name == 'from':
                sender = value
            elif name == 'to':
                # Split multiple recipients
                recipients = [r.strip() for r in value.split(',')]
            elif name == 'subject':
                subject = value
        
        # Extract content using a helper function that works with Gmail API format
        content = self._extract_content(email_data)
        
        if not content:
            print(f"Warning: Could not extract content for message {message_id}")
            content = "[No content available]"
        
        # Add message to memory
        try:
            self.memory.add_message(
                message_id=message_id,
                thread_id=thread_id,
                sender=sender,
                recipients=recipients,
                subject=subject,
                content=content,
                is_from_agent=is_from_agent
            )
            
            # Extract entities from email
            self._extract_entities_from_email(content, sender, subject)
            
            # Extract any potential relationships
            self._extract_relationships(content, sender)
            
            # Analyze thread topics
            topics = self.memory.analyze_thread_topics(thread_id)
            
            # Extract any action items or deadlines
            action_items = self._extract_action_items(content)
            
            # Get thread context
            thread_context = self.memory.get_thread_context(thread_id)
            
            # Return context for response generation
            return {
                'thread_context': thread_context,
                'topics': topics,
                'entities': self._get_relevant_entities(content),
                'action_items': action_items
            }
        except Exception as e:
            print(f"Error processing email for memory: {e}")
            return {
                'thread_context': f"Subject: {subject}\n\nFrom: {sender}",
                'topics': [],
                'entities': [],
                'action_items': []
            }
    
    def _extract_content(self, email_data: Dict[str, Any]) -> str:
        """Extract the content from Gmail API message format"""
        # First try to get content from snippet
        content = email_data.get('snippet', '')
        
        # If no snippet, try to get from payload
        if not content:
            try:
                payload = email_data.get('payload', {})
                
                # Try to get content from body data
                body_data = payload.get('body', {}).get('data')
                if body_data:
                    # Decode base64 content
                    import base64
                    decoded_data = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    content = decoded_data
                
                # If still no content, try to get from parts
                if not content:
                    parts = payload.get('parts', [])
                    for part in parts:
                        mime_type = part.get('mimeType', '')
                        if mime_type == 'text/plain' or mime_type == 'text/html':
                            part_body = part.get('body', {})
                            part_data = part_body.get('data')
                            if part_data:
                                # Decode base64 content
                                decoded_part = base64.urlsafe_b64decode(part_data).decode('utf-8')
                                content = decoded_part
                                break
            except Exception as e:
                print(f"Error extracting email content: {e}")
        
        # Decode HTML entities
        if content:
            import html
            content = html.unescape(content)
            
            # Remove HTML tags if present
            content = re.sub(r'<[^>]+>', ' ', content)
            
            # Clean up whitespace
            content = re.sub(r'\s+', ' ', content).strip()
        
        return content
    
    def _extract_entities_from_email(self, content: str, sender: str, subject: str) -> None:
        """Extract entities from email content and sender
        
        Identifies important entities in emails including:
        - People (sender, recipients, mentioned individuals)
        - Organizations (companies, institutions)
        - Projects (project names, initiatives)
        - Topics (subjects, themes of discussion)
        - Dates and deadlines (time-sensitive information)
        """
        # Extract sender as a person entity
        if sender:
            # Extract name from email format "Name <email@example.com>"
            name_match = re.match(r'^([^<]+)', sender)
            if name_match:
                name = name_match.group(1).strip()
                # Add sender as person entity
                self.memory.add_entity(name, "person", [sender])
                
                # Try to extract organization from email domain
                email_match = re.search(r'<([^>]+)>', sender)
                if email_match:
                    email = email_match.group(1)
                    domain = email.split('@')[-1]
                    if domain and '.' in domain and not domain.endswith(('.com', '.org', '.net', '.io', '.gov', '.edu')):
                        org_name = domain.split('.')[0].capitalize()
                        self.memory.add_entity(org_name, "organization")
                        # Add relationship between person and organization
                        person_id = f"person_{name.lower().replace(' ', '_')}"
                        org_id = f"organization_{org_name.lower().replace(' ', '_')}"
                        self.memory.add_relationship(person_id, org_id, "works_at")
        
        # Extract potential organizations
        org_patterns = [
            r'(?:at|from|with|for) ([A-Z][A-Za-z0-9\s]+(?:Inc|LLC|Ltd|Corp|Corporation|Company|Technologies|Systems|Solutions))',
            r'([A-Z][A-Za-z0-9\s]+(?:Inc|LLC|Ltd|Corp|Corporation|Company|Technologies|Systems|Solutions))',
            r'(?:at|from|with|for) ([A-Z][A-Za-z0-9\s&]+)'
        ]
        
        for pattern in org_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                org_name = match.strip()
                if org_name and len(org_name) > 3:  # Filter out very short names
                    self.memory.add_entity(org_name, "organization")
        
        # Extract potential projects
        project_patterns = [
            r'[Pp]roject\s+([A-Z][A-Za-z0-9\s]+)',
            r'[Pp]roject\s+([A-Z][A-Za-z0-9\s\-_]+)',
            r'[Tt]he\s+([A-Z][A-Za-z0-9\s]+)\s+[Pp]roject',
            r'[Ii]nitiative\s+([A-Z][A-Za-z0-9\s\-_]+)'
        ]
        
        for pattern in project_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                project_name = match.strip()
                if project_name and len(project_name) > 3:
                    self.memory.add_entity(project_name, "project")
        
        # Extract people mentioned in content
        person_patterns = [
            r'[A-Z][a-z]+\s+[A-Z][a-z]+',  # Simple name pattern (First Last)
            r'Mr\.\s+[A-Z][a-z]+',  # Mr. Last
            r'Ms\.\s+[A-Z][a-z]+',  # Ms. Last
            r'Mrs\.\s+[A-Z][a-z]+',  # Mrs. Last
            r'Dr\.\s+[A-Z][a-z]+'   # Dr. Last
        ]
        
        for pattern in person_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                person_name = match.strip()
                # Skip common words that might be capitalized
                common_words = ['This', 'That', 'These', 'Those', 'First', 'Last', 'Monday', 'Tuesday', 
                              'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', 'January',
                              'February', 'March', 'April', 'May', 'June', 'July', 'August',
                              'September', 'October', 'November', 'December']
                if (person_name and 
                    len(person_name) > 3 and
                    person_name not in common_words):
                    self.memory.add_entity(person_name, "person")
        
        # Extract topics from subject and content
        # The topic is often the main subject of the email
        if subject:
            # Remove common prefixes like Re:, Fwd:
            clean_subject = re.sub(r'^(Re|Fwd|FW|RE|FWD):\s*', '', subject).strip()
            if clean_subject:
                self.memory.add_entity(clean_subject, "topic")
        
        # Extract dates and deadlines
        date_patterns = [
            r'[Dd]eadline\s*:\s*([A-Za-z0-9\s,]+)',
            r'[Dd]ue\s*(?:by|on|date)?\s*:\s*([A-Za-z0-9\s,]+)',
            r'(?:on|by)\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?)',
            r'(?:on|by)\s+(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                date_str = match.strip()
                if date_str:
                    self.memory.add_entity(date_str, "date", metadata={"is_deadline": True})
    
    def _extract_relationships(self, content: str, sender: str) -> None:
        """Extract relationships between entities from email content
        
        Identifies connections like:
        - Person works at Organization
        - Person manages Project
        - Person knows Person
        - Organization sponsors Project
        """
        # First, get all entities in the email
        entity_ids = self.memory.extract_entities_from_text(content)
        if not entity_ids:
            return
        
        # Look for relationship patterns
        for i, entity_id1 in enumerate(entity_ids):
            entity1 = self.memory.get_entity_info(entity_id1)
            if not entity1:
                continue
            
            entity1_name = entity1.get('name', '')
            entity1_type = entity1.get('type', '')
            
            for j, entity_id2 in enumerate(entity_ids):
                if i == j:  # Skip self
                    continue
                    
                entity2 = self.memory.get_entity_info(entity_id2)
                if not entity2:
                    continue
                    
                entity2_name = entity2.get('name', '')
                entity2_type = entity2.get('type', '')
                
                # Common relationship patterns based on entity types
                if entity1_type == 'person' and entity2_type == 'organization':
                    # Person-organization relationships
                    if re.search(f"{entity1_name}.*(?:at|from|with|for).*{entity2_name}", content):
                        self.memory.add_relationship(entity_id1, entity_id2, "works_at")
                    elif re.search(f"{entity1_name}.*(?:leads|manages|runs|heads).*{entity2_name}", content):
                        self.memory.add_relationship(entity_id1, entity_id2, "leads")
                        
                elif entity1_type == 'person' and entity2_type == 'project':
                    # Person-project relationships
                    if re.search(f"{entity1_name}.*(?:manages|leads|runs|works on).*{entity2_name}", content):
                        self.memory.add_relationship(entity_id1, entity_id2, "manages")
                    elif re.search(f"{entity1_name}.*(?:contributes to|supports).*{entity2_name}", content):
                        self.memory.add_relationship(entity_id1, entity_id2, "contributes_to")
                        
                elif entity1_type == 'person' and entity2_type == 'person':
                    # Person-person relationships
                    if re.search(f"{entity1_name}.*(?:manages|supervises|leads).*{entity2_name}", content):
                        self.memory.add_relationship(entity_id1, entity_id2, "manages")
                    elif re.search(f"{entity1_name}.*(?:colleague|coworker|teammate).*{entity2_name}", content):
                        self.memory.add_relationship(entity_id1, entity_id2, "colleague_of")
                        
                elif entity1_type == 'organization' and entity2_type == 'project':
                    # Organization-project relationships
                    if re.search(f"{entity1_name}.*(?:sponsors|funds|supports).*{entity2_name}", content):
                        self.memory.add_relationship(entity_id1, entity_id2, "sponsors")
                    elif re.search(f"{entity1_name}.*(?:develops|creates|builds).*{entity2_name}", content):
                        self.memory.add_relationship(entity_id1, entity_id2, "develops")
    
    def _extract_action_items(self, content: str) -> List[Dict[str, Any]]:
        """Extract action items and requests from email content
        
        Returns a list of action items found in the email
        """
        action_items = []
        
        # Patterns that typically indicate action items
        action_patterns = [
            r'(?:[Pp]lease|[Cc]ould you|[Cc]an you)(?:\s+(?:[a-z]+\s+)?)?([^?\.]+\??)',
            r'(?:[Nn]eed to|[Ss]hould|[Mm]ust)(?:\s+(?:[a-z]+\s+)?)?([^?\.]+)',
            r'(?:[Ww]ould appreciate if you)(?:\s+(?:[a-z]+\s+)?)?([^?\.]+)',
            r'(?:[Aa]ction(?:\s+[Ii]tem)?:)(?:\s+(?:[a-z]+\s+)?)?([^?\.]+)',
            r'(?:[Tt]o-[Dd]o:)(?:\s+(?:[a-z]+\s+)?)?([^?\.]+)',
            r'(?:[Ff]ollow[\s-]*up:)(?:\s+(?:[a-z]+\s+)?)?([^?\.]+)'
        ]
        
        for pattern in action_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                item = match.strip()
                if item and len(item) > 10:  # Filter very short items
                    action_items.append({
                        "text": item,
                        "is_completed": False,
                        "source": "email",
                        "created_at": time.time()  # Add current timestamp
                    })
        
        return action_items
    
    def _get_relevant_entities(self, content: str) -> List[Dict[str, Any]]:
        """Get relevant entities for the current email content"""
        try:
            entity_ids = self.memory.extract_entities_from_text(content)
            entities = []
            
            for entity_id in entity_ids:
                entity_info = self.memory.get_entity_info(entity_id)
                if entity_info:
                    entities.append(entity_info)
            
            return entities
        except Exception as e:
            print(f"Error getting relevant entities: {e}")
            return []
    
    def get_memory_context(self, thread_id: str) -> str:
        """Get memory context for a thread to enhance AI responses"""
        if not thread_id:
            return ""
        
        try:
            # Get thread context
            thread_context = ""
            if hasattr(self.memory, 'get_thread_context'):
                thread_context = self.memory.get_thread_context(thread_id)
            
            # If no thread_context, we might not have any messages for this thread yet
            if not thread_context:
                return "No previous conversation history available."
            
            # Get entities mentioned in the thread
            thread = self.memory.threads.get(thread_id) if hasattr(self.memory, 'threads') else None
            if not thread:
                return thread_context
            
            # Collect all entity IDs mentioned in the thread
            entity_ids = set()
            
            # Check if thread has messages attribute
            if hasattr(thread, 'messages'):
                for message in thread.messages:
                    if hasattr(message, 'entities'):
                        entity_ids.update(message.entities)
            
            # Get entity information
            entity_context = ""
            for entity_id in entity_ids:
                if hasattr(self.memory, 'get_entity_info'):
                    entity_info = self.memory.get_entity_info(entity_id)
                    if entity_info:
                        entity_type = entity_info.get('type', '')
                        entity_name = entity_info.get('name', '')
                        
                        if entity_type and entity_name:
                            entity_context += f"\n- {entity_type.capitalize()}: {entity_name}"
                            
                            # Add relationship information
                            related = entity_info.get('related_entities', [])
                            for rel in related:
                                rel_name = rel.get('name', '')
                                rel_type = rel.get('relationship', '')
                                if rel_name and rel_type:
                                    entity_context += f"\n  - {rel_type.replace('_', ' ')} of {rel_name}"
            
            # Get topic information
            topic_context = ""
            if hasattr(thread, 'topics') and thread.topics:
                topic_context = "\n\nMain topics in this conversation:\n"
                for topic in thread.topics:
                    topic_context += f"- {topic}\n"
            
            # Combine contexts
            if entity_context or topic_context:
                memory_context = f"{thread_context}\n\nKey Information:"
                if entity_context:
                    memory_context += f"\nRelevant Entities:{entity_context}"
                if topic_context:
                    memory_context += topic_context
            else:
                memory_context = thread_context
                
            return memory_context
        except Exception as e:
            print(f"Error getting memory context: {e}")
            return "Unable to retrieve conversation history."
