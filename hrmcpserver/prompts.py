class Prompt:
  @staticmethod
  def prompt_resume_preprocess(role: str, resume: str, skillset: dict):
    prompt = f"""
      You are the hiring manager and reviewing the CV to onboard the candidate for the role : {role}:
    Instruction:
      - evaluate the resume content : {resume}
      - prepare the list of technical skill the candidate has based on the provided skillset : {skillset}
      - ensure all the list item is in lower case
      - return the final response as a list of string strictly for eg ["skill1", "skill2"] 
    """
    return prompt