from azure.servicebus import ServiceBusClient, ServiceBusMessage
import os
from dotenv import load_dotenv

load_dotenv()


connection_str = os.getenv("SERVICE_BUS_CONNECTION_STRING")

queue_name = "document-processing"
topic_name = 'document-events'

client = ServiceBusClient.from_connection_string(connection_str)

with client:
    sender = client.get_topic_sender(topic_name=topic_name)
    with sender:
        sender.send_messages(ServiceBusMessage("doc-201 processed", application_properties={"priority": "high"}))
        sender.send_messages(ServiceBusMessage("doc-202 processed", application_properties={"priotity": "low"}))
        
with client:
    r = client.get_subscription_receiver(topic_name=topic_name, subscription_name='indexing-subscriber', max_wait_time=10)
    with r:
        for msg in r:
            print("Indexing-subscriber got:", str(msg))
            r.complete_message(msg)
            

with client:
    r = client.get_subscription_receiver(topic_name=topic_name, subscription_name='notification-subscriber', max_wait_time=10)
    with r:
        for msg in r:
            print("notification-subscriber got:", str(msg))
            r.complete_message(msg)        
                
with client:
    r = client.get_queue_receiver(queue_name="document-processing", max_wait_time=15)
    with r:
        for msg in r:
            print("Received via Event Grid:", str(msg))
            r.complete_message(msg)
    

# with client:
#     sender = client.get_queue_sender(queue_name=queue_name)
#     with sender:
#         sender.send_messages(ServiceBusMessage("doc-101 uploaded, ready for processing"))
#         print("Message sent")
        

# with client:
#     receiver = client.get_queue_receiver(queue_name=queue_name, max_wait_time=10)
#     with receiver:
#         for msg in receiver:
#             print("Received:", str(msg))
#             receiver.complete_message(msg)
            
# with client:
#     sender = client.get_queue_sender(queue_name=queue_name)
#     with sender:
#         sender.send_messages(ServiceBusMessage("doc-102 uploaded, but corrupted file"))

# with client:
#     receiver = client.get_queue_receiver(queue_name=queue_name, max_wait_time=10)
#     with receiver:
#         for msg in receiver:
#             print("Received (unprocessable):", str(msg))
#             receiver.dead_letter_message(msg, reason="CorruptFile", error_description="File failed validation")

# with client:
#     dlq_receiver = client.get_queue_receiver(
#         queue_name=queue_name,
#         sub_queue="deadletter",
#         max_wait_time=10
#     )
#     with dlq_receiver:
#         for msg in dlq_receiver:
#             print("Found in DLQ:", str(msg), "| Reason:", msg.dead_letter_reason)
#             dlq_receiver.complete_message(msg)
            
