import asyncio
import parlant.sdk as p
from dotenv import load_dotenv

load_dotenv(".env")

# ------------------- Mock Tools -----------------------

async def authenticate_customer(method: str, identifier: str, secret: str = None) -> bool:
    """
    Simulates authentication.
    method: 'password', 'biometric', or 'otp'
    identifier: username or Aadhaar
    secret: password, fingerprint hash, or OTP code
    """
    valid = {
        ("password", "ramesh", "1234"),
        ("biometric", "aadhaar123", "1234"),
        ("otp", "aadhaar123", "1234"),
    }
    return (method, identifier, secret) in valid


async def get_account_info(user_id: str) -> dict:
    """
    Fetch customer info from DB (mock data for now).
    """
    db = {
        "ramesh": {"name": "Ramesh", "scheme": "PM-Kisan", "last_credit": "₹2000 on 23-Aug"},
        "aadhaar123": {"name": "Sita", "scheme": "NREGA", "last_credit": "₹2500 on 15-Aug"},
    }
    return db.get(user_id, {"error": "Account not found"})


# ------------------- Custom Retriever -----------------------

async def schemes_retriever(context: p.RetrieverContext) -> p.RetrieverResult:
    """
    Simple retriever to fetch scheme info from local file (schemes.txt).
    """
    try:
        query = context.interaction.last_customer_message.content.lower()
        with open("./data/schemes.txt", "r", encoding="utf-8") as f:
            docs = f.readlines()

        matches = [doc.strip() for doc in docs if query in doc.lower()]
        if matches:
            return p.RetrieverResult(matches)

        return p.RetrieverResult([])  # no results
    except Exception as e:
        return p.RetrieverResult([f"Retriever error: {str(e)}"])


# ------------------- Main Agent -----------------------

async def main():
    async with p.Server() as server:
        agent = await server.create_agent(
            name="PRAGATI - Propagation for Rural AI Gateway And Transaction Inquiry",
            description="""PRAGATI is a smart, AI-powered solution that helps rural
            communities check if government benefits (like NREGA wages or PM-Kisan subsidies)
            have arrived in their bank accounts. Citizens authenticate via password, biometric,
            or OTP, and get instant updates in their local language."""
        )

        # ----------- Terms (Synonyms for NREGA) ----------------
        await agent.create_term(
            name="NREGA",
            description="Mahatma Gandhi National Rural Employment Guarantee Act (MGNREGA): guarantees up to 100 days of wage employment per year for rural households.",
            synonyms=[
                "MGNREGA", "NREGA scheme", "100 days job scheme", "employment guarantee scheme",
                "मनरेगा", "मनरेगा योजना", "राष्ट्रीय ग्रामीण रोजगार गारंटी योजना", "महात्मा गांधी राष्ट्रीय ग्रामीण रोजगार गारंटी अधिनियम",
                "మహాత్మా గాంధీ జాతీయ గ్రామీణ ఉపాధి హామీ పథకం", "ఎన్ ఆర్ ఈ జి ఏ"
            ],
        )

        # ----------- Attach Retriever ----------------
        await agent.attach_retriever(schemes_retriever, id="schemes")

        # ----------- Tools ----------------
        await agent.register_tool(
            name="authenticate_customer",
            description="Authenticate customer via password, biometric, or OTP.",
            func=authenticate_customer,
        )

        await agent.register_tool(
            name="get_account_info",
            description="Retrieve customer account details (balance, scheme, last credit).",
            func=get_account_info,
        )

        # ----------- Guidelines ----------------

        # ---------------------------
        # Language Consistency Rule (High Priority)
        # ---------------------------
        await agent.create_guideline(
            condition="For every user interaction",
            action="IMPORTANT: Always detect the language of the user's message (e.g., English, Hindi, Telugu, Malayalam) and generate your entire response ONLY in that same language."
        )

        # ---------------------------
        # Greeting & Onboarding
        # ---------------------------
        await agent.create_guideline(
            condition="Customer greets (hello, hi, namaste, good morning, etc.)",
            action="Respond with a warm greeting in their language. Thank them for connecting with PRAGATI and offer help with NREGA, PM-Kisan, or other schemes."
        )

        # ---------------------------
        # Authentication
        # ---------------------------
        await agent.create_guideline(
            condition="Customer wants to log in or authenticate",
            action="Ask the customer which method they prefer: password, OTP, or biometric. Then call authenticate_customer tool to verify them.",
            tools=[authenticate_customer]
        )

        await agent.create_guideline(
            condition="Customer has failed authentication more than once",
            action="Politely inform them about retry limits and suggest visiting their local panchayat or customer service center for support."
        )

        # ---------------------------
        # Account / Wages Info
        # ---------------------------
        await agent.create_guideline(
            condition="Authenticated customer asks about NREGA balance, job card, or wage status",
            action="Call get_account_info tool and provide a clear response with scheme name, last credited amount, and pending wages if available.",
            tools=[get_account_info]
        )

        await agent.create_guideline(
            condition="Customer asks when their wages will be credited or why payment is delayed",
            action="Explain that NREGA payments are processed by local authorities and can sometimes be delayed. Advise them to check with their local panchayat office if the issue persists."
        )

        # ---------------------------
        # Scheme Information (Retriever)
        # ---------------------------
        await agent.create_guideline(
            condition="Customer asks about NREGA scheme details, eligibility, or application process",
            action="Query the 'schemes' retriever and explain the answer in simple words in the customer's preferred language."
        )

        await agent.create_guideline(
            condition="Customer asks about another government scheme (PM-Kisan, pensions, subsidies, etc.)",
            action="Query the 'schemes' retriever and summarize the relevant scheme information. Make it practical and easy to understand."
        )

        # ---------------------------
        # Complaints / Frustration Handling
        # ---------------------------
        await agent.create_guideline(
            condition="Customer expresses frustration, anger, or dissatisfaction about payments, services, or schemes",
            action="Acknowledge their concern empathetically, apologize for inconvenience, and guide them to practical next steps (like local authority, helpline, or grievance portal)."
        )

        # ---------------------------
        # General Queries
        # ---------------------------
        await agent.create_guideline(
            condition="Customer asks a general or unrelated question not about schemes",
            action="Politely explain that PRAGATI focuses on NREGA and government schemes, and redirect them back to supported topics."
        )

        # ----------- Interactive Chat Loop ----------------
        print("\nPRAGATI Agent is running. Type your questions below!")
        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in {"exit", "quit", "bye"}:
                print("Agent: Namaste! Thank you for using PRAGATI. Goodbye!")
                break
            response = await agent.chat(user_input)
            print("Agent:", response)


# ------------------- Run -----------------------
if __name__ == "__main__":
    asyncio.run(main())