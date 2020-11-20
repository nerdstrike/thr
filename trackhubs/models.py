"""
.. See the NOTICE file distributed with this work for additional information
   regarding copyright ownership.
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""
import logging
import time

from django.conf import settings
from django.db import models
from django_mysql.models import JSONField
import elasticsearch
from elasticsearch_dsl import connections
import trackhubs

logger = logging.getLogger(__name__)


class Species(models.Model):

    class Meta:
        db_table = "species"

    taxon_id = models.IntegerField()
    scientific_name = models.CharField(max_length=255, null=True)
    common_name = models.CharField(max_length=255, null=True)


class DataType(models.Model):

    class Meta:
        db_table = "data_type"

    data_type_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=45, default="genomics")


class FileType(models.Model):

    class Meta:
        db_table = "file_type"

    file_type_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    settings = JSONField()


class Visibility(models.Model):

    class Meta:
        db_table = "visibility"

    visibility_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=45)


class Hub(models.Model):

    class Meta:
        db_table = "hub"

    hub_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    short_label = models.CharField(max_length=255, null=True)
    long_label = models.CharField(max_length=255, null=True)
    url = models.CharField(max_length=255)
    description_url = models.URLField(null=True)
    email = models.EmailField(null=True)
    species = models.ForeignKey(Species, on_delete=models.CASCADE)
    data_type = models.ForeignKey(DataType, on_delete=models.CASCADE)
    # TODO: make sure that if the owner is deleted, the hubs are deleted too
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def get_trackdbs_ids(self):
        """
        Get all the trackdbs id belonging to the hub
        This function is used to delete trackdbs document from Elasticsearch
        since trackdbs in MySQL have the same ids in the Elasticsearch index
        """
        all_trackdbs_ids_list = []
        # look for all the genomes belonging to this hub
        genomes_list = Genome.objects.filter(hub_id=self.hub_id)

        for genome in genomes_list:
            # for each genome get the ids of trackdbs that will be deleted
            trackdbs_list = Trackdb.objects.filter(genome_id=genome.genome_id).values_list('pk', flat=True)
            all_trackdbs_ids_list.extend(list(trackdbs_list))

        logger.debug("IDs of all the trackdbs that will be deleted: {}".format(all_trackdbs_ids_list))
        return all_trackdbs_ids_list


class Genome(models.Model):

    class Meta:
        db_table = "genome"

    genome_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    trackdb_location = models.CharField(max_length=255)
    hub = models.ForeignKey(Hub, on_delete=models.CASCADE)


class Assembly(models.Model):

    class Meta:
        db_table = "assembly"

    assembly_id = models.AutoField(primary_key=True)
    accession = models.CharField(max_length=255)
    name = models.CharField(max_length=255, null=True)
    long_name = models.CharField(max_length=255, null=True)
    synonyms = models.CharField(max_length=255, null=True)
    genome = models.ForeignKey(Genome, on_delete=models.CASCADE)


class Trackdb(models.Model):

    class Meta:
        db_table = "trackdb"

    trackdb_id = models.AutoField(primary_key=True)
    public = models.BooleanField(default=False)
    description = models.TextField(null=True)
    version = models.CharField(default="v1.0", max_length=10)
    created = models.IntegerField(default=int(time.time()))
    updated = models.IntegerField(null=True)
    configuration = JSONField()
    status_message = models.CharField(max_length=45, null=True)
    status_last_update = models.CharField(max_length=45, null=True)
    source_url = models.CharField(max_length=255, null=True)
    source_checksum = models.CharField(max_length=255, null=True)
    assembly = models.ForeignKey(Assembly, on_delete=models.CASCADE)
    hub = models.ForeignKey(Hub, on_delete=models.CASCADE)
    genome = models.ForeignKey(Genome, on_delete=models.CASCADE)

    def update_trackdb_document(self, file_type, trackdb_data, trackdb_configuration, hub):
        """
        Update trackdb document in Elascticsearch with the additional data provided
        :param trackdb: trackdb object to be updated
        :param file_type: file type string associated with this track
        # TODO: write the proper query, file_type param will be removed
        :param trackdb_data: data array that will be added to the trackdb document
        :param trackdb_configuration: configuration object that will be added to the trackdb document
        :param hub: hub object associated with this trackdb
        # TODO: handle exceptions
        """
        try:
            es = connections.Elasticsearch()

            es.update(
                index='trackhubs',
                doc_type='doc',
                id=self.trackdb_id,
                refresh=True,
                body={
                    'doc': {
                        'file_type': {
                            # TODO: write a proper query/function (e.g get_file_type_count(trackdb))
                            file_type: trackhubs.models.FileType.objects.filter(name=file_type).count()
                        },
                        'data': trackdb_data,
                        'updated': int(time.time()),
                        'source': {
                            'url': self.source_url,
                            'checksum': ''
                        },
                        # Get the data type based on the hub info
                        'type': trackhubs.models.Hub.objects.filter(data_type_id=hub.data_type_id)
                            .values('data_type__name').first()
                            .get('data_type__name'),
                        'configuration': trackdb_configuration
                    }
                }
            )
            logger.info("Trackdb id {} is updated successfully".format(self.trackdb_id))

        except elasticsearch.exceptions.ConnectionError:
            logger.exception("There was an error while trying to connect to Elasticsearch. "
                             "Please make sure ES service is running and configured properly!")


class Track(models.Model):

    class Meta:
        db_table = "track"

    track_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    short_label = models.CharField(max_length=255, null=True)
    long_label = models.CharField(max_length=255, null=True)
    big_data_url = models.CharField(max_length=255, null=True)
    html = models.CharField(max_length=255, null=True)
    meta = models.CharField(max_length=255, null=True)
    additional_properties = JSONField()
    composite_parent = models.CharField(max_length=2, null=True)
    parent = models.ForeignKey('self', null=True, on_delete=models.CASCADE)
    trackdb = models.ForeignKey(Trackdb, on_delete=models.CASCADE)
    file_type = models.ForeignKey(FileType, on_delete=models.CASCADE)
    visibility = models.ForeignKey(Visibility, on_delete=models.CASCADE)
