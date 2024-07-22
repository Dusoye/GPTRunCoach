import os
from flask import Flask, render_template, request, jsonify
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, SelectField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, NumberRange
import anthropic
from dotenv import load_dotenv
import json
import re
import pandas as pd
from functools import lru_cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY")
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
    recent_race = StringField('Recent Race Result (if any)')
    units = SelectField('Units', choices=[('miles', 'Miles'), ('kilometers', 'Kilometers')], validators=[DataRequired()])

@lru_cache(maxsize=100)
def generate_running_plan(fitness_level, goal, weeks, days_per_week, time_goal, recent_race, units):
    """Generate a running plan using the Claude API with caching."""
    system_prompt = "You are an AI assistant tasked with creating personalized running training plans based on user responses to a set of questions. Your goal is to generate a comprehensive, tailored plan that meets the user's specific needs and goals."
    prompt = f"""
    Here are the user's responses to the questionnaire:

    A {weeks}-week running plan for a {fitness_level} runner 
    training for a {goal} race. The plan should include {days_per_week} 
    running days per week. Their time goal is {time_goal}. 
    A recent race result is {recent_race}, ignore this if it is not specified. 
    Set the distances in {units}

    Please provide a week-by-week breakdown of the training plan, including:
    1. Weekly mileage
    2. Types of runs (e.g., easy runs, long runs, speed work)
    3. Specific workouts
    4. Rest and cross-training days
    5. Gradual increase in intensity and volume
    6. Tapering period before the race

    Also, include general advice on nutrition, hydration, and injury prevention.

    Generate the training plan in JSON format, structured as follows:
    
    <json_structure>  
    {{
        "user_info": {{
            "fitness_level": "",
            "goal": "",
            "recent_race": {{
                "distance": "",
                "time": ""
            }},
            "training_duration_weeks": 0,
            "days_per_week": 0,
            "time_goal": "",
            "preferred_unit": ""
        }},
        "training_plan": [
            {{
                "week": 1,
                "workouts": [
                    {{
                        "day": 1,
                        "type": "",
                        "distance": "",
                        "description": ""
                    }}
                    // ... (repeat for each workout day)
                ]
            }}
            // ... (repeat for each week)
        ]
    }}
    </json_structure>
    
    For the \"type\" field in each workout, use one of the following categories:
    - Easy Run
    - Long Run
    - Tempo Run
    - Interval Training
    - Hill Repeats
    - Recovery Run
    - Cross-Training
    - Rest Day

    Ensure that the plan follows these guidelines:
    1. Gradually increase weekly mileage/distance
    2. Include a mix of workout types appropriate for the user's goal and fitness level
    3. Incorporate rest days and recovery runs to prevent overtraining
    4. For longer training plans (12+ weeks), include a tapering period before the goal race

    If the user has provided insufficient information or if there are any inconsistencies in their responses, make reasonable assumptions based on standard running training principles. For example, if a beginner aims for a marathon in 8 weeks, adjust the goal to a more realistic target like a 10K.

    Remember to maintain consistency in the unit of measurement (miles or kilometers) throughout the plan, as per the user's preference.

    Your final output should be valid JSON that can be easily parsed and used in web applications or downloaded by the user. Ensure that all fields are properly filled and the structure is maintained.
    """

    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=4000,
            temperature=0.1,
            system=system_prompt,
            messages=[        
                {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
                }
            ]
        )
        return response.content[0].text
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
            form.recent_race.data,
            form.units.data
        )
        if plan:
            json_match = re.search(r'\{.*\}', plan, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)

                before_json = plan[:json_match.start()].strip()
                after_json = plan[json_match.end():].strip()

                data = json.loads(json_text)

                user_info = data['user_info']
                training_plan = data['training_plan']
                
                user_info_df = pd.DataFrame([user_info])

                # Convert training plan to a DataFrame
                training_plan_list = []
                for week in training_plan:
                    week_num = week['week']
                    for workout in week['workouts']:
                        workout['week'] = week_num
                        training_plan_list.append(workout)
                training_plan_df = pd.DataFrame(training_plan_list)

                output = f"{before_json}\n\n"
                output += "User Information:\n"
                output += user_info_df.to_string(index=False)
                output += "\n\n"
                output += "Training Plan:\n"
                output += training_plan_df.to_string(index=False)
                output += "\n\n"
                output += after_json

                plan = output

    return render_template('index.html', form=form, plan=plan)


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429

if __name__ == '__main__':
    app.run(debug=True)