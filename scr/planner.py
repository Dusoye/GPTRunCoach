import os
from flask import Flask, render_template, request, jsonify
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, SelectField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, NumberRange
import anthropic
from dotenv import load_dotenv
import json
from functools import lru_cache
import time
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY", "fallback_secret_key")
csrf = CSRFProtect(app)

# Initialize the Anthropic client
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Setup rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

class RunningPlanForm(FlaskForm):
    fitness_level = SelectField('Fitness Level', choices=[('Beginner', 'Beginner'), ('Intermediate', 'Intermediate'), ('Advanced', 'Advanced')], validators=[DataRequired()])
    goal = StringField('Running Goal', validators=[DataRequired()])
    weeks = IntegerField('Training Weeks', validators=[DataRequired(), NumberRange(min=1, max=52)])
    days_per_week = IntegerField('Running Days per Week', validators=[DataRequired(), NumberRange(min=1, max=7)])
    time_goal = StringField('Time Goal (if any)')
    units = SelectField('Units', choices=[('miles', 'Miles'), ('kilometers', 'Kilometers')], validators=[DataRequired()])

@lru_cache(maxsize=100)
def generate_running_plan(fitness_level, goal, weeks, days_per_week, time_goal, units):
    """Generate a running plan using the Claude API with caching."""
    prompt = f"""
    You are an AI assistant tasked with creating personalized running training plans based on user responses to a set of questions. Your goal is to generate a comprehensive, tailored plan that meets the user's specific needs and goals.

    Here are the user's responses to the questionnaire:
    
    Create a {weeks}-week running plan for a {fitness_level} runner 
    training for a {goal} race. The plan should include {days_per_week} 
    running days per week. Their time goal is {time_goal}. 
    Use {units} for distance measurements.

    Please provide a week-by-week breakdown of the training plan in JSON format. Each week should be an object with the following structure:
    {{
        "week": <week number>,
        "total_distance": <total distance for the week>,
        "workouts": [
            {{
                "day": <day of week>,
                "type": <type of run>,
                "distance": <distance>,
                "description": <brief description of the workout>
            }},
            ...
        ]
    }}

    Also include a "general_advice" key in the main JSON object with advice on nutrition, hydration, and injury prevention.

    Ensure the JSON is valid and can be parsed by Python's json.loads() function.
    """

    try:
        response = client.completions.create(
            model="claude-3-opus-20240229",
            prompt=prompt,
            max_tokens_to_sample=2000,
        )
        return json.loads(response.completion)
    except Exception as e:
        app.logger.error(f"Error generating running plan: {str(e)}")
        return None

@app.route('/', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def index():
    form = RunningPlanForm()
    if form.validate_on_submit():
        plan = generate_running_plan(
            form.fitness_level.data,
            form.goal.data,
            form.weeks.data,
            form.days_per_week.data,
            form.time_goal.data,
            form.health_concerns.data,
            form.units.data
        )
        if plan:
            return jsonify(plan)
        else:
            return jsonify({"error": "Failed to generate plan. Please try again later."}), 500

    return render_template('index.html', form=form)

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429

if __name__ == '__main__':
    app.run(debug=True)