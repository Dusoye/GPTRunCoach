import os
from flask import Flask, render_template, request, jsonify, send_file, flash
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, SelectField, IntegerField
from wtforms.validators import DataRequired, NumberRange
import anthropic
from dotenv import load_dotenv
import json
from functools import lru_cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import csv
from io import StringIO, BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

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
    units = SelectField('Units', choices=[('Miles', 'Miles'), ('Kilometers', 'Kilometers')], validators=[DataRequired()])

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
                ]
            }}
        ],
        "additional_advice": ""
    }}
    
    For the "type" field in each workout, use one of the following categories:
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

    If the user has provided insufficient information or if there are any inconsistencies in their responses, make reasonable assumptions based on standard running training principles.

    Remember to maintain consistency in the unit of measurement (miles or kilometers) throughout the plan, as per the user's preference.

    Your final output should be valid JSON that can be easily parsed and used in web applications or downloaded by the user. Ensure that all fields are properly filled and the structure is maintained.
    """

    try:
        response = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=8000,
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

def create_user_info_table(user_info):
    table = "<table class='table table-dark'>"
    for key, value in user_info.items():
        if key == 'recent_race':
            table += f"<tr><th>{key.replace('_', ' ').title()}</th><td>{value['distance']} - {value['time']}</td></tr>"
        else:
            table += f"<tr><th>{key.replace('_', ' ').title()}</th><td>{value}</td></tr>"
    table += "</table>"
    return table

def create_training_plan_table(training_plan):
    table = "<table class='table table-dark'>"
    table += "<thead><tr><th>Week</th><th>Day</th><th>Type</th><th>Distance</th><th>Description</th></tr></thead><tbody>"
    for week in training_plan:
        for workout in week['workouts']:
            table += f"<tr><td>{week['week']}</td><td>{workout['day']}</td><td>{workout['type']}</td><td>{workout['distance']}</td><td>{workout['description']}</td></tr>"
    table += "</tbody></table>"
    return table

def generate_pdf(plan_data):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    heading_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Title
    elements.append(Paragraph("Your Running Plan", title_style))
    elements.append(Spacer(1, 12))
    
    # User Information
    elements.append(Paragraph("User Information", heading_style))
    user_info = [
        ["Fitness Level", plan_data['user_info']['fitness_level']],
        ["Goal", plan_data['user_info']['goal']],
        ["Recent Race", f"{plan_data['user_info']['recent_race']['distance']} - {plan_data['user_info']['recent_race']['time']}"],
        ["Training Duration", f"{plan_data['user_info']['training_duration_weeks']} weeks"],
        ["Days Per Week", str(plan_data['user_info']['days_per_week'])],
        ["Time Goal", plan_data['user_info']['time_goal']],
        ["Preferred Unit", plan_data['user_info']['preferred_unit']]
    ]
    user_table = Table(user_info)
    user_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    elements.append(user_table)
    elements.append(Spacer(1, 12))
    
        # Training Plan
    elements.append(Paragraph("Training Plan", heading_style))
    plan_data_list = [['Week', 'Day', 'Type', 'Distance', 'Description']]
    for week in plan_data['training_plan']:
        for workout in week['workouts']:
            plan_data_list.append([
                str(week['week']),
                str(workout['day']),
                workout['type'],
                workout['distance'],
                Paragraph(workout['description'], normal_style)
            ])
    
    col_widths = [0.5*inch, 0.5*inch, 1*inch, 0.75*inch, 5.25*inch]  # Adjust these values as needed
    plan_table = Table(plan_data_list, colWidths=col_widths, repeatRows=1)
    plan_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('WORDWRAP', (0, 0), (-1, -1), True),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(plan_table)
    elements.append(Spacer(1, 12))
    
    # Additional Advice
    elements.append(Paragraph("Additional Advice", heading_style))
    elements.append(Paragraph(plan_data['additional_advice'], normal_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

@app.route('/download_plan_pdf/<plan_id>')
def download_plan_pdf(plan_id):
    plan_data = app.config.get('latest_plan')
    
    if not plan_data:
        flash("Plan not found. Please generate a new plan.", "error")
        return redirect(url_for('index'))

    try:
        pdf_buffer = generate_pdf(plan_data)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='running_plan.pdf'
        )
    except Exception as e:
        app.logger.error(f"Error generating PDF: {str(e)}")
        flash("An error occurred while generating the PDF. Please try again.", "error")
        return redirect(url_for('index'))


@app.route('/download_plan/<plan_id>')
def download_plan(plan_id):
    # Retrieve the plan data based on the plan_id
    # For now, we'll use a simple in-memory storage. In a real app, you'd use a database.
    plan_data = app.config.get('latest_plan')
    
    if not plan_data:
        return "Plan not found", 404

    # Create a CSV file in memory
    output = StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Week', 'Day', 'Type', 'Distance', 'Description'])
    
    # Write data
    for week in plan_data['training_plan']:
        for workout in week['workouts']:
            writer.writerow([
                week['week'],
                workout['day'],
                workout['type'],
                workout['distance'],
                workout['description']
            ])
    
    # Convert to BytesIO
    mem = BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    
    return send_file(
        mem,
        mimetype='text/csv',
        as_attachment=True,
        download_name='running_plan.csv'
    )


@app.route('/', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def index():
    form = RunningPlanForm()
    if form.validate_on_submit():
        plan_json = generate_running_plan(
            form.fitness_level.data,
            form.goal.data.lower(),
            form.weeks.data,
            form.days_per_week.data,
            form.time_goal.data,
            form.recent_race.data.lower(),
            form.units.data
        )
        if plan_json:
            try:
                data = json.loads(plan_json)
                # Store the latest plan in app config (this is a simple solution, not suitable for production)
                app.config['latest_plan'] = data
                return render_template('result_bright.html', 
                                       user_info=data['user_info'],
                                       training_plan=data['training_plan'],
                                       additional_advice=data['additional_advice'],
                                       plan_id='latest')  # In a real app, use a unique identifier
            except json.JSONDecodeError:
                return jsonify({"error": "Failed to parse the generated plan. Please try again."}), 500
        else:
            return jsonify({"error": "Failed to generate plan. Please try again later."}), 500

    return render_template('index_bright.html', form=form)

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429

if __name__ == '__main__':
    app.run(debug=True)