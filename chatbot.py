import streamlit as st
import oci
from typing import Optional
from oci.exceptions import ServiceError, RequestException  #temproray


st.set_page_config(page_title="OCI Gen-AI Chatbot", page_icon="💬", layout="centered")
st.title("OCI Gen-AI Chatbot for Telco")
st.caption("Ask a question to the Oracle Gen-AI Powered Agent. Click ‘Reset chat...’ to start a new session.")

#Configuration: Load credentials from Streamlit Secrets

def build_oci_config() -> dict:
    sec = st.secrets["DEFAULT"]
    cfg = {
        "user": sec["user_ocid"],
        "tenancy": sec["tenancy_ocid"],
        "fingerprint": sec["fingerprint"],
        "region": sec["region"],
        "key_content": sec["private_key"],
    #    "pass_phrase": sec["pass_phrase"],
    }
    #if sec.get("pass_phrase"):
     #   cfg["pass_phrase"] = sec["pass_phrase"]
    
    oci.config.validate_config(cfg)
    
    return cfg

#Runtime constants (update AGENT_ENDPOINT_ID)
def get_runtime_endpoint(region: str) -> str:
    return f"https://generativeaiagents-runtime.{region}.oci.oraclecloud.com"
AGENT_ENDPOINT_ID = "ocid1.genaiagentendpoint.oc1.us-chicago-1.amaaaaaac7x6gxiasdz374pvot4e3weyblbvm57zsphuxbjtagabglpiuaja"
    

#Client lifecycle
def get_client() -> oci.generative_ai_agent_runtime.GenerativeAiAgentRuntimeClient:
    if "ga_client" not in st.session_state:
        cfg = build_oci_config()
        endpoint = get_runtime_endpoint(cfg["region"])
        st.session_state.ga_client = oci.generative_ai_agent_runtime.GenerativeAiAgentRuntimeClient(
                cfg,
                service_endpoint=endpoint,
        )
    return st.session_state.ga_client

#Agent session lifecycle             
def ensure_session_id(client) -> str:
    if "agent_session_id" not in st.session_state:
        try:
                resp = client.create_session(
                        create_session_details=oci.generative_ai_agent_runtime.models.CreateSessionDetails(
                                display_name="User Session",
                                description="Session created by Streamlit app",
                        ),
                        agent_endpoint_id=AGENT_ENDPOINT_ID,
                        retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY,
                )
                st.session_state.agent_session_id = resp.data.id

#------------------------------------------        
#        except oci.exceptions.ServiceError as e:
#                st.error(f"CreateSession failed (status={e.status}, code={e.code}): {e.message}")
#------------------------------------------

        except RequestException:
            st.error("Network error calling Agents runtime. Check endpoint/region and public visibility.")
            raise
        except ServiceError as e:
            st.error(f"CreateSession failed: status={e.status}, code={e.code}, message={e.message}")
            st.write("Request ID:", e.request_id)
            st.write("Endpoint called:", e.request_endpoint)
            raise
        finally:
            st.session_state["create_session_attempted"] = True
    return st.session_state.agent_session_id

#------------------------------------------
#                raise
#        finally:

#                st.session_state["create_session_attempted"] = True
#    return st.session_state.agent_session_id
#------------------------------------------

def end_session(client):
    sess_id = st.session_state.get("agent_session_id")
    if not sess_id:
        return
    try:
        client.end_session(
                agent_endpoint_id=AGENT_ENDPOINT_ID,
                session_id=sess_id,
                retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY,
        )
    except oci.exceptions.ServiceError:
        pass
    finally:
        st.session_state.pop("agent_session_id", None)



#Chat with the agent
def chat_once(user_message: str) -> str:
    client = get_client()
    session_id = ensure_session_id(client)
    try:
        resp = client.chat(
                agent_endpoint_id=AGENT_ENDPOINT_ID,
                chat_details=oci.generative_ai_agent_runtime.models.ChatDetails(
                        user_message=user_message,
                        session_id=session_id,
                ),
                retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY,
        )
        return resp.data.message.content.text
    except oci.exceptions.ServiceError as e:
        st.error(f"Chat failed (status={e.status}, code={e.code}): {e.message}")
        return "Sorry, I ran into an error while contacting the agent."
    finally:
        st.session_state["last_prompt"] = user_message


#Streamlit chat UI and state

if "messages" not in st.session_state:
    st.session_state.messages = []
col1, col2 = st.columns([1, 6])
with col1:
    if st.button("Reset chat", type="secondary"):
        if "ga_client" in st.session_state:
                try:
                        end_session(st.session_state.ga_client)
                except Exception:
                        pass
        st.session_state.messages = []
        st.rerun()
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
prompt = st.chat_input("How can I help?")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        answer = chat_once(prompt)
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
