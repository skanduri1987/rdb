import datetime

import json

import os

from pathlib import Path

import googleapiclient.discovery

from dotenv import load_dotenv

from flask import Flask, render_template, flash, redirect, url_for, request

from sqlalchemy.dialects.mysql import VARCHAR

from flask_apscheduler import APScheduler

from flask_bootstrap import Bootstrap5

from flask_htmx import HTMX

from flask_migrate import Migrate

from flask_sock import Sock

from flask_sqlalchemy import SQLAlchemy

from flask_wtf import FlaskForm, CSRFProtect

from google.api_core.exceptions import NotFound

#from google.cloud import compute_v1, monitoring_v3, container_v1, gke_backup_v1

from google.cloud import compute_v1, monitoring_v3

from google.oauth2 import service_account

#from simplesqlite import SimpleSQLite

from sqlalchemy import inspect, func

from wtforms import StringField, SubmitField, TextAreaField, DateField

from wtforms.validators import DataRequired

#from werkzeug import url_encode



load_dotenv()





def object_as_dict(obj):

    return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}





def create_tables():

    with app.app_context():

        db.create_all()





class Config:

    DEBUG = True

    SCHEDULER_API_ENABLED = True

    SCHEDULER_EXECUTORS = {"default": {"type": "threadpool", "max_workers": 20}}

    SCHEDULER_JOB_DEFAULTS = {

        "coalesce": True,

        "max_instances": 1,

        "replace_existing": False,

    }

    BOOTSTRAP_SERVE_LOCAL = True

    SECRET_KEY = "asgdsg6dsfg6sdfg6sd+g6ds6+fg6+dfs"

    SOCK_SERVER_OPTIONS = {"ping_interval": 25}

    SQLALCHEMY_DATABASE_URI = (

        f"mysql+pymysql://svcrdb:bigdata123@localhost/rdb"

    )





app = Flask(__name__)

app.config.from_object(Config)





bootstrap = Bootstrap5(app)

htmx = HTMX(app)

csrf = CSRFProtect(app)

scheduler = APScheduler(app=app)

db = SQLAlchemy(app)

migrate = Migrate(app, db)

sock = Sock(app)





class Credential(db.Model):

    __tablename__ = "credentials"



    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    project_id = db.Column(db.String(length=255), nullable=False, unique=True)

    json = db.Column(db.TEXT(length=10000000), nullable=False)





class Vm(db.Model):

    __tablename__ = "vms"



    id = db.Column(db.Integer)

    project_id = db.Column(db.String(length=255))

    name = db.Column(db.String(length=255), primary_key=True)

    labels = db.Column(db.String(length=255))

    snapshot_statuses = db.Column(db.String(length=255))

    latest_snapshot = db.Column(db.String(length=255))

    disk_size = db.Column(db.Integer)

    cpu_usage = db.Column(db.Numeric)

    memory_usage = db.Column(db.Numeric)

    on_state = db.Column(db.Integer, default=0)





class Database(db.Model):

    __tablename__ = "sqldbs"



    id = db.Column(db.Integer, primary_key=True)

    project_id = db.Column(db.String(length=255))

    name = db.Column(db.String(length=255), unique=True)

    labels = db.Column(db.String(length=255))

    statuses = db.Column(db.String(length=255))

    latest_backup = db.Column(db.String(length=255))

    disk_size = db.Column(db.Integer)

    on_state = db.Column(db.Integer, default=0)





class Cluster(db.Model):

    __tablename__ = "gkeclusters"



    id = db.Column(db.String(length=255), primary_key=True, unique=True)

    name = db.Column(db.String(length=255))

    backup_states = db.Column(db.String(length=255))

    resource_count = db.Column(db.Integer)

    latest_backup = db.Column(db.String(length=255))

    labels = db.Column(db.String(length=255))





class Alert(db.Model):

    __tablename__ = "alert"



    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    message = db.Column(db.String(length=255), nullable=False)

    created_at = db.Column(db.String(length=255))





class CredentialsForm(FlaskForm):

    project_id = StringField("Project ID", validators=[DataRequired()])

    service_account_json = TextAreaField(

        "Service Account Json", validators=[DataRequired()], render_kw={"rows": 6}

    )

    submit = SubmitField("Save")





class FilterForm(FlaskForm):

    class Meta:

        csrf = False



    start_date = DateField("Start Date")

    end_date = DateField("End Date")

    submit = SubmitField("Filter")





@app.route("/")

def index():

    start_date = request.args.get(

        "start_date",

        default=(datetime.date.today() - datetime.timedelta(days=7)).strftime(

            "%Y-%m-%d"

        ),

    )

    end_date = request.args.get(

        "end_date",

        default=datetime.date.today().strftime("%Y-%m-%d"),

    )

    form = FilterForm(

        data={

            "start_date": datetime.datetime.strptime(start_date, "%Y-%m-%d").date(),

            "end_date": datetime.datetime.strptime(end_date, "%Y-%m-%d").date(),

        }

    )

    vm_running_count = Vm.query.filter_by(on_state=1).count()

    vm_backup_count = Vm.query.count()

    if vm_backup_count:

        ratio = vm_running_count / vm_backup_count

        if ratio < 0.5:

            vm_health_color = "bg-danger-subtle"

        elif ratio >= 0.75:

            vm_health_color = "bg-success-subtle"

        else:

            vm_health_color = "bg-warning-subtle"

    else:

        vm_health_color = "bg-secondary-subtle"

    dbs_backup_count = Database.query.count()

    db_running_count = Database.query.filter_by(on_state=1).count()

    cluster_backup_count = Cluster.query.count()

    if dbs_backup_count:

        ratio = db_running_count / dbs_backup_count

        if ratio < 0.5:

            db_health_color = "bg-danger-subtle"

        elif ratio >= 0.75:

            db_health_color = "bg-success-subtle"

        else:

            db_health_color = "bg-warning-subtle"

    else:

        db_health_color = "bg-secondary-subtle"

    alerts = [

         alert

         for alert in Alert.query.filter(func.date(Alert.created_at) <= end_date)

         .filter(func.date(Alert.created_at) >= start_date)

         .order_by(Alert.id.desc())

         .limit(5)

         .all()

    ]



   # alerts = [



        

    #    { "message" : "absciad", "created_at" : "Album1" },

     #   { "message" : "dbhkausdsidfsi", "created_at" : "Album2" }





    #]



    return render_template(

        "index.html",

        form=form,

        vm_backup_count=vm_backup_count,

        vm_running_count=vm_running_count,

        vm_health_color=vm_health_color,

        dbs_backup_count=dbs_backup_count,

        db_running_count=db_running_count,

        db_health_color=db_health_color,

        cluster_backup_count=cluster_backup_count,

        alerts=alerts,

        now=datetime.datetime.now(),

    )





@app.route("/credentials/", methods=["GET", "POST"])

def credentials():

    data = Credential.query.all()

    form = CredentialsForm()

    if form.validate_on_submit():

        db.session.add(

            Credential(

                project_id=form.project_id.data, json=form.service_account_json.data

            )

        )

        db.session.commit()

        flash("Credentials saved successfully.")

        return redirect(url_for("credentials"))



    return render_template("credentials.html", form=form, data=data)





@app.route("/credentials/delete/<string:project_id>/", methods=["POST"])

def delete_credential(project_id):

    Vm.query.filter_by(project_id=project_id).delete()

    Database.query.filter_by(project_id=project_id).delete()

    Credential.query.filter_by(project_id=project_id).delete()

    db.session.commit()



    flash("Credentials deleted successfully.")

    return redirect(url_for("credentials"))





@app.route("/backups/vms")

def list_vm_backups():

    data = Vm.query.all()



    def map_vm(item):

        item_dict = object_as_dict(item)

        item_dict["snapshot_statuses"] = json.loads(item_dict["snapshot_statuses"])

        labels = json.loads(item_dict["labels"])

        if "productname" in labels:

            item_dict["category"] = labels["productname"]

        else:

            item_dict["category"] = ""

        return item_dict



    return render_template("vm_backups.html", data=map(map_vm, data))





@app.route("/backups/dbs")

def list_db_backups():

    data = Database.query.all()

    new_data = []

    for item in data:

        item = object_as_dict(item)

        item["statuses"] = json.loads(item["statuses"])

        if item["latest_backup"]:

            if (

                datetime.datetime.strptime(

                    item["latest_backup"], "%Y-%m-%dT%H:%M:%S.%fZ"

                ).date()

                == datetime.date.today()

            ):

                item["todays_backup"] = item["statuses"][0] == "SUCCESSFUL"

            else:

                item["todays_backup"] = ""



        labels = json.loads(item["labels"])

        if labels and "productname" in labels:

            item["category"] = labels["productname"]

        else:

            item["category"] = ""



        new_data.append(item)

    return render_template(

        "db_backups.html",

        data=new_data,

    )





@app.route("/backups/clusters")

def list_cluster_backups():

    data = Cluster.query.all()

    new_data = []

    for item in data:

        item = object_as_dict(item)

        item["states"] = json.loads(item["backup_states"])

        labels = json.loads(item["labels"])

        if labels and "productname" in labels:

            item["category"] = labels["productname"]

        else:

            item["category"] = ""

        new_data.append(item)

    return render_template(

        "cluster_backups.html",

        data=new_data,

    )





@sock.route("/echo")

def echo(ws):

    while True:

        data = ws.receive()

        ws.send(data)





def get_vm_data(project_id, cred_json, instance):

    print(f"Checking data for vm {instance['id']}")

    cred = service_account.Credentials.from_service_account_info(json.loads(cred_json))

    snapshot_client = compute_v1.SnapshotsClient(credentials=cred)

    request = compute_v1.ListSnapshotsRequest()

    request.project = project_id

    request.max_results = 15

    request.filter = f"(source_disk = \"{instance['disk']}\") AND (auto_created = true)"

    result = [item for item in snapshot_client.list(request)]

    result.sort(

        key=lambda val: datetime.datetime.fromisoformat(val.creation_timestamp),

        reverse=True,

    )

    snapshot_statuses = []

    latest_snapshot = None

    disk_size = 0

    memory_usage = -1.0

    cpu_usage = -1.0



    if result:

        latest_snapshot = result[0].creation_timestamp



    for item in result[:2]:

        snapshot_statuses.insert(0, item.status)

        if not disk_size:

            disk_size = int(item.disk_size_gb)



    interval = monitoring_v3.TimeInterval()

    now = datetime.datetime.now()

    interval.start_time = now - datetime.timedelta(minutes=2)

    interval.end_time = now

    monitoring_client = monitoring_v3.MetricServiceClient(credentials=cred)

    request = monitoring_v3.ListTimeSeriesRequest()

    request.name = f"projects/{project_id}"

    request.interval = interval

    request.filter = (

        'metric.type = "agent.googleapis.com/memory/percent_used" '

        f'AND resource.labels.instance_id = "{instance["id"]}"'

    )

    try:

        data = [item for item in monitoring_client.list_time_series(request)]

        if data:

            memory_usage = data[0].points[0].value.double_value

    except NotFound:

        pass



    request.filter = (

        'metric.type = "compute.googleapis.com/instance/cpu/utilization" '

        f'AND resource.labels.instance_id = "{instance["id"]}"'

    )

    try:

        data = [item for item in monitoring_client.list_time_series(request)]

        if data:

            cpu_usage = data[0].points[0].value.double_value

    except NotFound:

        pass



    with app.app_context():

        vm = Vm.query.filter_by(id=instance["id"]).first()

        labels = json.dumps(dict(instance["labels"]))

        if vm:

            obj = vm

            if obj.on_state == 1 and not (instance["status"] == "RUNNING"):

                db.session.add(

                    Alert(

                        message=f"Vm {instance['name']} is offline.",

                        created_at=str(datetime.datetime.now()),

                    )

                )

            elif obj.on_state == 0 and instance["status"] == "RUNNING":

                db.session.add(

                    Alert(

                        message=f"Vm {instance['name']} is now online.",

                        created_at=str(datetime.datetime.now()),

                    )

                )

            vm.snapshot_statuses = json.dumps(snapshot_statuses)

            vm.latest_snapshot = latest_snapshot

            vm.labels = labels

            vm.disk_size = disk_size

            vm.memory_usage = memory_usage

            vm.cpu_usage = cpu_usage

            vm.on_state = int(instance["status"] == "RUNNING")

            db.session.add(vm)

        else:

            db.session.add(

                Vm(

                    project_id=project_id,

                    id=str(instance["id"]),

                    name=instance["name"],

                    labels=labels,

                    snapshot_statuses=json.dumps(snapshot_statuses),

                    latest_snapshot=latest_snapshot,

                    disk_size=disk_size,

                    memory_usage=memory_usage,

                    cpu_usage=cpu_usage,

                    on_state=int(instance["status"] == "RUNNING"),

                )

            )

        db.session.commit()

    print(f"Done checking data for vm {instance['id']}")





def get_db_backups(project_id, cred_json, db_instance):

    print(f"Checking backups for db {db_instance['name']}")

    cred = service_account.Credentials.from_service_account_info(

        json.loads(cred_json),

        scopes=["https://www.googleapis.com/auth/sqlservice.admin"],

    )

    sqladmin = googleapiclient.discovery.build("sqladmin", "v1", credentials=cred)

    response = (

        sqladmin.backupRuns()

        .list(project=project_id, instance=db_instance["name"])

        .execute()

    )

    backup_statuses = []

    latest_backup = None



    for item in response["items"][:5]:

        backup_statuses.insert(0, item["status"])

        if not latest_backup:

            latest_backup = item["startTime"]



    with app.app_context():

        obj = Database.query.filter_by(name=db_instance["name"]).first()

        labels = json.dumps(dict(db_instance["labels"]))

        if obj:

            if obj.on_state == 1 and not (db_instance["is_running"]):

                db.session.add(

                    Alert(

                        message=f"DB {db_instance['name']} is offline.",

                        created_at=str(datetime.datetime.now()),

                    )

                )

            elif obj.on_state == 0 and db_instance["is_running"]:

                db.session.add(

                    Alert(

                        message=f"DB {db_instance['name']} is now online.",

                        created_at=str(datetime.datetime.now()),

                    )

                )



            obj.statuses = json.dumps(backup_statuses)

            obj.latest_backup = latest_backup

            obj.disk_size = db_instance["disk_size"]

            obj.labels = labels

            obj.on_state = int(db_instance["is_running"])

            db.session.add(obj)

        else:

            db.session.add(

                Database(

                    project_id=project_id,

                    name=db_instance["name"],

                    labels=labels,

                    statuses=json.dumps(backup_statuses),

                    latest_backup=latest_backup,

                    disk_size=int(db_instance["disk_size"]),

                    on_state=int(db_instance["is_running"]),

                )

            )

        db.session.commit()

        print(f"Done checking backups for db {db_instance['name']}")





def get_gke_backups(project_id, cred_json, cluster):

    print(f"Checking backup for cluster {cluster['id']}")

    cred = service_account.Credentials.from_service_account_info(json.loads(cred_json))

    backup_for_gke_client = gke_backup_v1.BackupForGKEClient(credentials=cred)

    request = gke_backup_v1.ListBackupPlansRequest()

    request.parent = "projects/mohit-devops/locations/-"

    request.filter = (

        f'(cluster = "projects/{project_id}/locations/{cluster["location"]}/clusters/{cluster["name"]}") '

        f"AND (deactivated = false)"

    )

    data = [item for item in backup_for_gke_client.list_backup_plans(request)]

    data.sort(key=lambda val: val.create_time, reverse=True)

    if data:

        name = data[0].name

        request = gke_backup_v1.ListBackupsRequest()

        request.parent = f"{name}"

        request.order_by = "create_time desc"

        data = backup_for_gke_client.list_backups(request)

        latest_backup = None

        resource_count = None

        backup_states = []

        data = [item for item in data]

        for item in data[:5]:

            backup_states.insert(0, item.state.name)

            print(backup_states)

            if not latest_backup:

                latest_backup = item.create_time

            if not resource_count:

                resource_count = item.resource_count

        with app.app_context():

            obj = Cluster.query.filter_by(id=cluster["id"]).first()

            labels = json.dumps(dict(cluster["labels"]))

            if obj:

                obj.backup_states = json.dumps(backup_states)

                obj.latest_backup = str(latest_backup)

                obj.labels = labels

                obj.resource_count = resource_count

                db.session.add(obj)

            else:

                db.session.add(

                    Cluster(

                        id=cluster["id"],

                        name=cluster["name"],

                        backup_states=json.dumps(backup_states),

                        latest_backup=str(latest_backup),

                        resource_count=resource_count,

                        labels=labels,

                    )

                )

            db.session.commit()

    print(f"Done checking backup for cluster {cluster['id']}")





def check_infra_status_for_project(project_id, cred_json):

    print(f"{project_id}: Checking infra...")

    cred = service_account.Credentials.from_service_account_info(json.loads(cred_json))

    instance_client = compute_v1.InstancesClient(credentials=cred)

    request = compute_v1.AggregatedListInstancesRequest()

    request.project = project_id

    agg_list = instance_client.aggregated_list(request=request)

    instances = []

    for _, response in agg_list:

        if response.instances:

            instance: compute_v1.Instance

            for instance in response.instances:

                print(f" - {instance.name} ({instance.machine_type})")

                instances.append(

                    {

                        "id": instance.id,

                        "name": instance.name,

                        "disk": instance.disks[0].source,

                        "labels": instance.labels,

                        "status": instance.status,

                    }

                )

    for instance in instances:

        scheduler.add_job(

            f"vm-data-job-{instance['id']}",

            get_vm_data,

            args=(project_id, cred_json, instance),

            max_instances=1,

            replace_existing=False,

        )



    """cluster_manager_client = container_v1.ClusterManagerClient(credentials=cred)

    request = container_v1.ListClustersRequest()

    request.parent = f"projects/{project_id}/locations/-"

    data = cluster_manager_client.list_clusters(request)

    for item in data.clusters:

        scheduler.add_job(

            f"gke-backup-job-{item.id}",

            get_gke_backups,

            args=(

                project_id,

                cred_json,

                {

                    "id": item.id,

                    "name": item.name,

                    "location": item.location,

                    "labels": item.resource_labels,

                },

            ),

        )"""



    cred = service_account.Credentials.from_service_account_info(

        json.loads(cred_json),

        scopes=["https://www.googleapis.com/auth/sqlservice.admin"],

    )

    sqladmin = googleapiclient.discovery.build("sqladmin", "v1", credentials=cred)

    response = sqladmin.instances().list(project=project_id).execute()

    for item in response["items"]:

        db_instance = {

            "name": item["name"],

            "labels": item["settings"].get("userLabels", {}),

            "state": item["state"],

            "is_running": item["settings"].get("activationPolicy", None) == "ALWAYS",

        }

        if "currentDiskSize" in item:

            db_instance["disk_size"] = item["currentDiskSize"]

        else:

            db_instance["disk_size"] = item["settings"]["dataDiskSizeGb"]

        scheduler.add_job(

            f"backup-job-{db_instance['name']}",

            get_db_backups,

            args=(project_id, cred_json, db_instance),

        )

    print(f"{project_id}: Done checking  infra.")





@scheduler.task(

    "interval", id="check_infra_status", seconds=120, misfire_grace_time=900

)

def check_infra_status():

    with app.app_context():

        data = Credential.query.all()

        count = Credential.query.count()



        print(f"Found {count} credential(s)")

        for cred in data:

            scheduler.add_job(

                f"{cred.project_id}-job",

                check_infra_status_for_project,

                args=(cred.project_id, cred.json),

            )

        print("Done checking infra...")





create_tables()

scheduler.start()



if __name__ == "__main__":

    app.run(debug=True)
