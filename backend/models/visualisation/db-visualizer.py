from backend.models.tables import User, Session, DailyBonusLog, ChoiceLog
from sqlalchemy_data_model_visualizer import generate_data_model_diagram, add_web_font_and_interactivity

if __name__ == '__main__':
    # Suppose these are your SQLAlchemy data models defined above in the usual way, or imported from another file:
    models = [User, Session, DailyBonusLog, ChoiceLog]
    output_file_name = 'db-graph'
    generate_data_model_diagram(models, output_file_name)
    add_web_font_and_interactivity('db-graph.svg', 'db-graph.svg')
