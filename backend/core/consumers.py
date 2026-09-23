import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Conversation,Message,Notification
class ChatConsumer(AsyncWebsocketConsumer):
 async def connect(self):
  self.conversation_id=self.scope['url_route']['kwargs']['conversation_id'];self.room=f'conversation_{self.conversation_id}'
  if not self.scope['user'].is_authenticated or not await self.authorized():return await self.close(code=4403)
  await self.channel_layer.group_add(self.room,self.channel_name);await self.accept(subprotocol='jwt')
 async def disconnect(self,code):await self.channel_layer.group_discard(self.room,self.channel_name)
 async def receive(self,text_data):
  body=json.loads(text_data).get('body','').strip()
  if body:
   msg=await self.save_message(body);await self.channel_layer.group_send(self.room,{'type':'chat.message','id':msg.id,'body':body,'sender':self.scope['user'].id,'created_at':msg.created_at.isoformat()})
 async def chat_message(self,event):await self.send(text_data=json.dumps(event))
 @database_sync_to_async
 def authorized(self):return Conversation.objects.filter(pk=self.conversation_id,participants=self.scope['user']).exists()
 @database_sync_to_async
 def save_message(self,body):
  message=Message.objects.create(conversation_id=self.conversation_id,sender=self.scope['user'],body=body)
  conversation=Conversation.objects.get(pk=self.conversation_id)
  for other in conversation.participants.exclude(pk=self.scope['user'].pk):Notification.objects.create(user=other,kind='NEW_MESSAGE',title='New message',body=body[:180])
  return message
