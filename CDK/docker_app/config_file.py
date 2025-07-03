class Config:
    # Stack name
    # Change this value if you want to create a new instance of the stack
    STACK_NAME = "aws-strands-react-chatbot"
    
    # Put your own custom value here to prevent ALB to accept requests from
    # other clients that CloudFront. You can choose any random string.
    CUSTOM_HEADER_VALUE = "ReAct_Chatbot_Security_Header_2024"    
    
