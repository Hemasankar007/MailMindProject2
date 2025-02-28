import json
import os
import time
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field, asdict
import re

@dataclass
class Entity:
    """Represents a recognized entity in conversations"""
    name: str
    type: str  # person, organization, project, topic, etc.
    aliases: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    
    def update_seen(self):
        """Update the last seen timestamp"""
        self.last_seen = time.time()
    
    def add_alias(self, alias: str):
        """Add an alternative name for this entity"""
        if alias and alias.strip():
            self.aliases.add(alias.strip())
    
    def matches(self, text: str) -> bool:
        """Check if the text matches this entity or any of its aliases"""
        text = text.lower()
        if self.name.lower() in text:
            return True
        return any(alias.lower() in text for alias in self.aliases)

@dataclass
class Relationship:
    """Represents a relationship between two entities"""
    entity1_id: str
    entity2_id: str
    relationship_type: str  # colleague, manager, client, etc.
    strength: float = 0.0  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    
    def update_seen(self):
        """Update the last seen timestamp"""
        self.last_seen = time.time()
    
    def strengthen(self, amount: float = 0.1):
        """Strengthen the relationship"""
        self.strength = min(1.0, self.strength + amount)

@dataclass
class ConversationMessage:
    """Represents a single message in a conversation"""
    message_id: str
    thread_id: str
    sender: str
    recipients: List[str]
    subject: str
    content: str
    timestamp: float
    is_from_agent: bool = False
    entities: List[str] = field(default_factory=list)  # Entity IDs mentioned in this message

@dataclass
class ConversationThread:
    """Represents a thread of conversation"""
    thread_id: str
    subject: str
    participants: Set[str] = field(default_factory=set)
    messages: List[ConversationMessage] = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)
    topics: List[str] = field(default_factory=list)
    
    def add_message(self, message: ConversationMessage):
        """Add a message to the thread"""
        self.messages.append(message)
        self.participants.add(message.sender)
        for recipient in message.recipients:
            self.participants.add(recipient)
        self.last_updated = time.time()
        
    def get_context_summary(self, max_messages: int = 5) -> str:
        """Get a summary of the conversation context for AI prompting"""
        # Sort messages by timestamp
        sorted_messages = sorted(self.messages, key=lambda m: m.timestamp)
        
        # Get the most recent messages up to max_messages
        recent_messages = sorted_messages[-max_messages:] if len(sorted_messages) > max_messages else sorted_messages
        
        # Format the messages into a context summary
        context = f"Subject: {self.subject}\n\n"
        for msg in recent_messages:
            sender = "You (Sofia)" if msg.is_from_agent else msg.sender
            context += f"From: {sender}\n"
            context += f"Date: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(msg.timestamp))}\n"
            context += f"{msg.content}\n\n"
            
        return context

class ConversationMemoryStore:
    """Stores and manages conversation memory and context"""
    
    def __init__(self, storage_path: str = None):
        """Initialize the conversation memory store"""
        if storage_path is None:
            # Default to a file in the same directory as this module
            current_dir = os.path.dirname(os.path.abspath(__file__))
            storage_path = os.path.join(current_dir, "conversation_memory.json")
        
        self.storage_path = storage_path
        self.entities: Dict[str, Entity] = {}
        self.relationships: Dict[str, Relationship] = {}
        self.threads: Dict[str, ConversationThread] = {}
        
        # Load existing data if available
        self.load()
    
    def load(self):
        """Load conversation memory from storage"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                
                # Load entities
                for entity_id, entity_data in data.get('entities', {}).items():
                    self.entities[entity_id] = Entity(
                        name=entity_data['name'],
                        type=entity_data['type'],
                        aliases=set(entity_data.get('aliases', [])),
                        metadata=entity_data.get('metadata', {}),
                        first_seen=entity_data.get('first_seen', time.time()),
                        last_seen=entity_data.get('last_seen', time.time())
                    )
                
                # Load relationships
                for rel_id, rel_data in data.get('relationships', {}).items():
                    self.relationships[rel_id] = Relationship(
                        entity1_id=rel_data['entity1_id'],
                        entity2_id=rel_data['entity2_id'],
                        relationship_type=rel_data['relationship_type'],
                        strength=rel_data.get('strength', 0.0),
                        metadata=rel_data.get('metadata', {}),
                        first_seen=rel_data.get('first_seen', time.time()),
                        last_seen=rel_data.get('last_seen', time.time())
                    )
                
                # Load threads
                for thread_id, thread_data in data.get('threads', {}).items():
                    thread = ConversationThread(
                        thread_id=thread_id,
                        subject=thread_data['subject'],
                        participants=set(thread_data.get('participants', [])),
                        last_updated=thread_data.get('last_updated', time.time()),
                        topics=thread_data.get('topics', [])
                    )
                    
                    # Load messages
                    for msg_data in thread_data.get('messages', []):
                        message = ConversationMessage(
                            message_id=msg_data['message_id'],
                            thread_id=thread_id,
                            sender=msg_data['sender'],
                            recipients=msg_data['recipients'],
                            subject=msg_data['subject'],
                            content=msg_data['content'],
                            timestamp=msg_data['timestamp'],
                            is_from_agent=msg_data.get('is_from_agent', False),
                            entities=msg_data.get('entities', [])
                        )
                        thread.messages.append(message)
                    
                    self.threads[thread_id] = thread
                    
            except Exception as e:
                print(f"Error loading conversation memory: {e}")
    
    def save(self):
        """Save conversation memory to storage"""
        try:
            # Convert data to JSON-serializable format
            data = {
                'entities': {},
                'relationships': {},
                'threads': {}
            }
            
            # Save entities
            for entity_id, entity in self.entities.items():
                data['entities'][entity_id] = {
                    'name': entity.name,
                    'type': entity.type,
                    'aliases': list(entity.aliases),
                    'metadata': entity.metadata,
                    'first_seen': entity.first_seen,
                    'last_seen': entity.last_seen
                }
            
            # Save relationships
            for rel_id, rel in self.relationships.items():
                data['relationships'][rel_id] = {
                    'entity1_id': rel.entity1_id,
                    'entity2_id': rel.entity2_id,
                    'relationship_type': rel.relationship_type,
                    'strength': rel.strength,
                    'metadata': rel.metadata,
                    'first_seen': rel.first_seen,
                    'last_seen': rel.last_seen
                }
            
            # Save threads
            for thread_id, thread in self.threads.items():
                thread_data = {
                    'subject': thread.subject,
                    'participants': list(thread.participants),
                    'last_updated': thread.last_updated,
                    'topics': thread.topics,
                    'messages': []
                }
                
                # Save messages
                for msg in thread.messages:
                    msg_data = {
                        'message_id': msg.message_id,
                        'thread_id': msg.thread_id,
                        'sender': msg.sender,
                        'recipients': msg.recipients,
                        'subject': msg.subject,
                        'content': msg.content,
                        'timestamp': msg.timestamp,
                        'is_from_agent': msg.is_from_agent,
                        'entities': msg.entities
                    }
                    thread_data['messages'].append(msg_data)
                
                data['threads'][thread_id] = thread_data
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # Write to file
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving conversation memory: {e}")
    
    def add_entity(self, name: str, entity_type: str, aliases: List[str] = None) -> str:
        """Add a new entity and return its ID"""
        entity_id = f"{entity_type}_{name.lower().replace(' ', '_')}"
        
        # Check if entity already exists
        if entity_id in self.entities:
            # Update existing entity
            self.entities[entity_id].update_seen()
            if aliases:
                for alias in aliases:
                    self.entities[entity_id].add_alias(alias)
        else:
            # Create new entity
            entity = Entity(
                name=name,
                type=entity_type,
                aliases=set(aliases) if aliases else set()
            )
            self.entities[entity_id] = entity
        
        return entity_id
    
    def add_relationship(self, entity1_id: str, entity2_id: str, relationship_type: str) -> str:
        """Add a relationship between two entities and return its ID"""
        # Ensure both entities exist
        if entity1_id not in self.entities or entity2_id not in self.entities:
            raise ValueError("Both entities must exist before creating a relationship")
        
        # Create a consistent ID for the relationship
        rel_id = f"{min(entity1_id, entity2_id)}_{max(entity1_id, entity2_id)}_{relationship_type}"
        
        # Check if relationship already exists
        if rel_id in self.relationships:
            # Update existing relationship
            self.relationships[rel_id].update_seen()
            self.relationships[rel_id].strengthen()
        else:
            # Create new relationship
            relationship = Relationship(
                entity1_id=entity1_id,
                entity2_id=entity2_id,
                relationship_type=relationship_type
            )
            self.relationships[rel_id] = relationship
        
        return rel_id
    
    def add_thread(self, thread_id: str, subject: str) -> ConversationThread:
        """Add a new conversation thread or get existing one"""
        if thread_id in self.threads:
            # Update existing thread
            self.threads[thread_id].last_updated = time.time()
            return self.threads[thread_id]
        else:
            # Create new thread
            thread = ConversationThread(
                thread_id=thread_id,
                subject=subject
            )
            self.threads[thread_id] = thread
            return thread
    
    def add_message(self, message_id: str, thread_id: str, sender: str, 
                   recipients: List[str], subject: str, content: str, 
                   is_from_agent: bool = False) -> ConversationMessage:
        """Add a message to a thread and extract entities"""
        # Ensure thread exists
        thread = self.add_thread(thread_id, subject)
        
        # Create message
        timestamp = time.time()
        message = ConversationMessage(
            message_id=message_id,
            thread_id=thread_id,
            sender=sender,
            recipients=recipients,
            subject=subject,
            content=content,
            timestamp=timestamp,
            is_from_agent=is_from_agent
        )
        
        # Extract entities from content
        entity_ids = self.extract_entities_from_text(content)
        message.entities = entity_ids
        
        # Add message to thread
        thread.add_message(message)
        
        # Save changes
        self.save()
        
        return message
    
    def extract_entities_from_text(self, text: str) -> List[str]:
        """Extract known entities from text and return their IDs"""
        entity_ids = []
        
        # Check for existing entities
        for entity_id, entity in self.entities.items():
            if entity.matches(text):
                entity_ids.append(entity_id)
                entity.update_seen()
        
        return entity_ids
    
    def get_thread_context(self, thread_id: str, max_messages: int = 5) -> str:
        """Get conversation context for a thread"""
        if thread_id in self.threads:
            return self.threads[thread_id].get_context_summary(max_messages)
        return ""
    
    def get_entity_info(self, entity_id: str) -> Dict[str, Any]:
        """Get information about an entity including its relationships"""
        if entity_id not in self.entities:
            return {}
        
        entity = self.entities[entity_id]
        related_entities = []
        
        # Find relationships involving this entity
        for rel_id, rel in self.relationships.items():
            if rel.entity1_id == entity_id:
                other_entity_id = rel.entity2_id
                if other_entity_id in self.entities:
                    related_entities.append({
                        'entity_id': other_entity_id,
                        'name': self.entities[other_entity_id].name,
                        'type': self.entities[other_entity_id].type,
                        'relationship': rel.relationship_type,
                        'strength': rel.strength
                    })
            elif rel.entity2_id == entity_id:
                other_entity_id = rel.entity1_id
                if other_entity_id in self.entities:
                    related_entities.append({
                        'entity_id': other_entity_id,
                        'name': self.entities[other_entity_id].name,
                        'type': self.entities[other_entity_id].type,
                        'relationship': rel.relationship_type,
                        'strength': rel.strength
                    })
        
        # Return entity info with relationships
        return {
            'id': entity_id,
            'name': entity.name,
            'type': entity.type,
            'aliases': list(entity.aliases),
            'first_seen': entity.first_seen,
            'last_seen': entity.last_seen,
            'related_entities': related_entities
        }
    
    def find_entities_by_type(self, entity_type: str) -> List[str]:
        """Find all entities of a specific type"""
        return [entity_id for entity_id, entity in self.entities.items() 
                if entity.type == entity_type]
    
    def find_entity_by_name(self, name: str) -> Optional[str]:
        """Find an entity by name or alias"""
        name_lower = name.lower()
        for entity_id, entity in self.entities.items():
            if entity.name.lower() == name_lower:
                return entity_id
            for alias in entity.aliases:
                if alias.lower() == name_lower:
                    return entity_id
        return None
    
    def get_recent_threads(self, limit: int = 10) -> List[ConversationThread]:
        """Get the most recently updated conversation threads"""
        sorted_threads = sorted(
            self.threads.values(), 
            key=lambda t: t.last_updated, 
            reverse=True
        )
        return sorted_threads[:limit]
    
    def analyze_thread_topics(self, thread_id: str) -> List[str]:
        """Analyze and extract topics from a conversation thread"""
        if thread_id not in self.threads:
            return []
        
        thread = self.threads[thread_id]
        
        # Combine all message content
        all_content = " ".join([msg.content for msg in thread.messages])
        
        # Simple keyword-based topic extraction
        # In a real implementation, this would use NLP or an AI model
        topics = []
        common_topics = [
            "meeting", "project", "deadline", "report", "question",
            "help", "issue", "problem", "update", "request", "information"
        ]
        
        for topic in common_topics:
            if topic in all_content.lower():
                topics.append(topic)
        
        # Update thread topics
        thread.topics = topics
        return topics