from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, validators
from form.RequiredIf import RequiredIf
from flask import current_app as app
from model.DB import db_session
from model.Package import Package
from sqlalchemy import literal


class SubmitPackageForm(FlaskForm):
    type = SelectField('Repository Type',
                       choices=[('', '-- Choose Repo Type --')] + [(src.__name__, src.__name__)
                                                                   for src in app.config["package_sources"]],
                       validators=[validators.InputRequired()])
    owner = StringField('Owner',
                        description='Name of the package repository owner',
                        render_kw={'placeholder': 'ueffel', 'required': True},
                        validators=[validators.InputRequired()])
    repo = StringField('Repository',
                       description='Name of the package repository',
                       render_kw={'placeholder': 'Keypirinha-PackageControl', 'required': True},
                       validators=[validators.InputRequired()])
    path = StringField('Path',
                       description='Path to the .keypirinha-package file',
                       render_kw={'placeholder': 'path/to/package.keypirinha-package'},
                       validators=[RequiredIf(type='GithubFile'),
                                   validators.Regexp(r'^.+\.keypirinha-package$',
                                                     message='Path must end with ".keypirinha-package"')])

    @staticmethod
    def exists_package(owner, repo, repo_type, path=None):
        qry = db_session.query(Package).filter(Package.owner == owner,
                                               Package.repo == repo,
                                               Package.ptype == repo_type,
                                               Package.path == path).exists()
        return db_session.query(qry).scalar()

    def validate(self):
        if not super(SubmitPackageForm, self).validate():
            return False

        if self.exists_package(self.owner.data,
                               self.repo.data,
                               self.type.data,
                               self.path.data if self.path.data else None):
            self._errors = ['This package already exists in the repository']
            return False

        package = Package(self.owner.data, self.repo.data, self.type.data, self.path.data)
        source_type = next((package_source for package_source in app.config["package_sources"]
                            if package_source.__name__ == package.ptype), None)
        source = source_type(package)

        if not source.is_available():
            self._errors = ['The package source is not available.']
            return False

        return True

    def required_if_fields(self):
        result = []
        for field_name, field in self._fields.items():
            required_ifs = [validator for validator in field.validators if isinstance(validator, RequiredIf)]
            for required_if in required_ifs:
                for condition_key, condition_value in required_if.conditions.items():
                    required_if_field = {
                        "if_field": condition_key,
                        "if_field_value": condition_value,
                        "required": field_name
                    }
                    result.append(required_if_field)
        return result
