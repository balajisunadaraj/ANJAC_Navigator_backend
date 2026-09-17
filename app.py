from flask import Flask, jsonify, request
from flask_cors import CORS
from supabase import create_client
from dotenv import load_dotenv
import os

from google import genai
from google.genai import types


# ============================================================
# Load environment variables
# ============================================================

load_dotenv()


# ============================================================
# Gemini configuration
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("Gemini API key loaded:", bool(GEMINI_API_KEY))

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing in .env or Render Environment Variables")

gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ============================================================
# Supabase configuration
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

FLASK_PORT = int(
    os.getenv("PORT", os.getenv("FLASK_PORT", 5000))
)


if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing in .env")


if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY is missing in .env")


# ============================================================
# Create Flask application
# ============================================================

app = Flask(__name__)

CORS(app)


# ============================================================
# Connect to Supabase
# ============================================================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ============================================================
# Test Flask
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "success": True,
        "message": "ANJAC Campus Navigator API is running"
    })


# ============================================================
# Get all locations
# ============================================================

@app.route("/api/locations", methods=["GET"])
def get_locations():

    try:

        response = (
            supabase
            .table("locations")
            .select("*")
            .order("id")
            .execute()
        )

        return jsonify({
            "success": True,
            "locations": response.data
        })

    except Exception as e:

        print("LOCATION ERROR:", str(e))

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# Get Route
#
# Supports:
#
# 1. Normal route
#       M Block -> C Block
#
# 2. Reverse route
#       C Block -> M Block
#
# If reverse route is selected,
# route points are reversed.
# ============================================================

@app.route("/api/route", methods=["GET"])
def get_route():

    try:

        # ----------------------------------------------------
        # Get current location ID
        # ----------------------------------------------------

        current_location_id = request.args.get(
            "current_location_id",
            type=int
        )

        # ----------------------------------------------------
        # Get destination ID
        # ----------------------------------------------------

        destination = request.args.get(
            "destination",
            type=int
        )

        # ----------------------------------------------------
        # Validate input
        # ----------------------------------------------------

        if current_location_id is None or destination is None:

            return jsonify({
                "success": False,
                "error": "current_location_id and destination are required"
            }), 400

        print("------------------------------------------")
        print("Route request received")
        print("Current Location ID:", current_location_id)
        print("Destination ID:", destination)

        # ====================================================
        # STEP 1
        # Search for normal route
        # ====================================================

        route_response = (
            supabase
            .table("routes")
            .select("*")
            .eq(
                "current_location_id",
                current_location_id
            )
            .eq(
                "destination",
                destination
            )
            .limit(1)
            .execute()
        )

        reversed_route = False

        # ====================================================
        # STEP 2
        # Search reverse route if normal route not found
        # ====================================================

        if not route_response.data:

            print("Normal route not found.")
            print("Searching for reverse route...")

            route_response = (
                supabase
                .table("routes")
                .select("*")
                .eq(
                    "current_location_id",
                    destination
                )
                .eq(
                    "destination",
                    current_location_id
                )
                .limit(1)
                .execute()
            )

            if route_response.data:

                reversed_route = True

                print("Reverse route found.")

        # ====================================================
        # STEP 3
        # Route not found
        # ====================================================

        if not route_response.data:

            print("Route not found.")

            return jsonify({
                "success": False,
                "error": "Route not found"
            }), 404

        # ====================================================
        # STEP 4
        # Get route
        # ====================================================

        route = route_response.data[0]

        route_id = route["id"]

        print("Route ID:", route_id)
        print("Reversed:", reversed_route)

        # ====================================================
        # STEP 5
        # Get route points
        # ====================================================

        points_response = (
            supabase
            .table("route_points")
            .select("*")
            .eq(
                "route_id",
                route_id
            )
            .order(
                "sequence"
            )
            .execute()
        )

        points = points_response.data

        # ====================================================
        # STEP 6
        # Reverse route points if necessary
        # ====================================================

        if reversed_route:

            print("Reversing route points...")

            points.reverse()

        # ====================================================
        # STEP 7
        # Print route points
        # ====================================================

        print("Route points:")

        for point in points:

            print(
                point.get("point_name"),
                "Sequence:",
                point.get("sequence")
            )

        print("------------------------------------------")

        # ====================================================
        # STEP 8
        # Return route
        # ====================================================

        return jsonify({

            "success": True,

            "route": route,

            "route_id": route_id,

            "reversed": reversed_route,

            "points": points

        })

    except Exception as e:

        print("ROUTE ERROR:", str(e))

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# Get Campus Events
# ============================================================

@app.route("/api/events", methods=["GET"])
def get_events():

    try:

        response = (
            supabase
            .table("events")
            .select("id,title,date,location,description")
            .order("date")
            .execute()
        )

        events = []

        for event in response.data:

            events.append({

                "id": event.get("id"),

                "title": event.get("title"),

                "date": event.get("date"),

                "location": event.get("location"),

                "description": event.get("description")

            })

        return jsonify({

            "success": True,

            "events": events

        })

    except Exception as e:

        print("EVENT ERROR:", str(e))

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


# ============================================================
# Gemini AI Chat
# ============================================================

@app.route("/api/chat", methods=["POST"])
def chat():

    try:

        # ----------------------------------------------------
        # Get JSON data
        # ----------------------------------------------------

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "error": "JSON body is required"
            }), 400

        # ----------------------------------------------------
        # Get user message
        # ----------------------------------------------------

        user_message = data.get(
            "message",
            ""
        ).strip()

        # ----------------------------------------------------
        # Validate message
        # ----------------------------------------------------

        if not user_message:

            return jsonify({
                "success": False,
                "error": "Message is required"
            }), 400

        print("------------------------------------------")
        print("Gemini request received")
        print("User message:", user_message)

        # ====================================================
        # Gemini request
        # ====================================================

        response = gemini_client.models.generate_content(

            model="gemini-3.6-flash",

            contents=user_message,

            config=types.GenerateContentConfig(

                system_instruction="""

You are the AI assistant for ANJAC Campus Navigator.

You help students navigate
Ayya Nadar Janaki Ammal College campus.

Your responsibilities:

1. Answer questions about the campus.

2. Help students select a destination.

3. When the user wants navigation,
   ask for their current location if it is not known.

4. Explain campus locations clearly.

5. Keep responses short and friendly.

Known campus locations:

Gate
M Block
C Block
Admin Block
Statue
Library
W Block
G Block
Auditorium
Indoor
Canteen 1
Canteen 2
N Block
B Hostel
G Hostel
E Block
PHS

Important rules:

- Do not invent campus locations.
- Do not invent routes.
- Do not invent buildings.
- Do not claim that navigation has started.
- The Unity application is responsible for starting navigation.
- If you do not know something, clearly say that you do not know.
- Keep responses concise because the response may be spoken aloud.
- Be helpful and conversational.
- Do not provide unnecessary long explanations.

Example:

User:
Where is the library?

Assistant:
The Library is one of the main locations on the ANJAC campus.

User:
I want to go to the library.

Assistant:
Sure! What is your current location?

"""

            )

        )

        # ====================================================
        # Get Gemini response
        # ====================================================

        reply = response.text

        print("Gemini reply:", reply)

        print("------------------------------------------")

        return jsonify({

            "success": True,

            "reply": reply

        })

    except Exception as e:

        # ====================================================
        # Gemini error logging
        # ====================================================

        print("==========================================")
        print("GEMINI ERROR:")
        print(repr(e))
        print("==========================================")

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


# ============================================================
# Start Flask Server
# ============================================================

if __name__ == "__main__":

    print("==========================================")
    print("Starting ANJAC Campus Navigator API...")
    print("Server running on port:", FLASK_PORT)
    print("==========================================")

    app.run(

        host="0.0.0.0",

        port=FLASK_PORT,

        debug=False

    )