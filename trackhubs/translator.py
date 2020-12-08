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

import json
import logging
import time

import django
from django.contrib.auth.models import User

import trackhubs
from trackhubs.constants import DATA_TYPES, FILE_TYPES, VISIBILITY
from trackhubs.models import Trackdb
from trackhubs.parser import parse_file_from_url

logger = logging.getLogger(__name__)


def save_fake_species():
    """
    Save fake species, this will be replaced with a proper function later
    """
    # TODO: Replace this with a proper one
    try:
        if not trackhubs.models.Species.objects.filter(taxon_id=9606).exists():
            sp = trackhubs.models.Species(
                taxon_id=9606,
                scientific_name='Homo sapiens'
            )
            sp.save()
    except django.db.utils.OperationalError:
        logger.exception('Error trying to connect to Elasticsearch')


def get_datatype_filetype_visibility(unique_col, object_name, file_type=False):
    """
    Get object (can be DataType, FileType or Visibility) by name
    Create one if it doesn't exist?
    TODO: merge it with get_obj_if_exist() by adding create_if_not_exist param
    :param unique_col: hub,genomes or trackdb url
    :param object_name: can be DataType, FileType or Visibility
    :param file_type: is set to true if we are parsing genomes
    :returns: either the existing object or the new created one
    """
    if file_type:
        # trim the type in case we have extra info e.g 'type bigBed 6 +'
        unique_col = get_first_word(unique_col)

    existing_obj = object_name.objects.filter(name=unique_col).first()
    return existing_obj


def get_obj_if_exist(unique_col, object_name, file_type=False):
    """
    Returns the object if it exists otherwise it returns None
    :param unique_col: hub,genomes or trackdb url
    :param object_name: can be DataType, FileType or Visibility
    :param file_type: is set to true if we are parsing genomes
    :returns: either the existing object or the new created one
    """
    if file_type:
        # trim the type in case we have extra info e.g 'type bigBed 6 +'
        unique_col = get_first_word(unique_col)

    existing_obj = object_name.objects.filter(name=unique_col).first()
    if existing_obj:
        return existing_obj
    else:
        return None


def save_datatype_filetype_visibility(name_list, object_name):
    """
    Save all constants rows of DataType, FileType and Visibility
    in their corresponding table
    name_list: list of the values to be stored
    object_name: either DataType, FileType or Visibility
    TODO: this function should be executed once just after creating the database
    """
    name_list_obj = []
    for name in name_list:
        if not object_name.objects.filter(name=name).exists():
            obj = object_name(name=name)
            name_list_obj.append(obj)

    object_name.objects.bulk_create(name_list_obj)


def save_hub(hub_dict, data_type, current_user, species=00):
    """
    Save the hub in MySQL DB if it doesn't exist already
    :param hub_dict: hub dictionary containing all the parsed info
    :param data_type: either specified by the user in the POST request
    or the default one ('genomics')
    :param species: the species associated with this hub
    :param current_user: the submitter (current user) id
    # TODO: work on adding species
    :returns: the new created hub
    """
    # TODO: Add try expect if the 'hub' or 'url' is empty
    new_hub_obj = trackhubs.models.Hub(
        name=hub_dict['hub'],
        short_label=hub_dict.get('shortLabel'),
        long_label=hub_dict.get('longLabel'),
        url=hub_dict['url'],
        description_url=hub_dict.get('descriptionUrl'),
        email=hub_dict.get('email'),
        data_type=trackhubs.models.DataType.objects.filter(name=data_type).first(),
        species_id=1,
        owner_id=current_user.id
    )
    new_hub_obj.save()
    return new_hub_obj


def save_genome(genome_dict, hub):
    """
    Save the genome in MySQL DB  if it doesn't exist already
    :param genome_dict: genome dictionary containing all the parsed info
    :param hub: hub object associated with this genome
    :returns: either the existing genome or the new created one
    """
    existing_genome_obj = trackhubs.models.Genome.objects.filter(name=genome_dict['genome']).first()
    if existing_genome_obj:
        return existing_genome_obj
    else:
        new_genome_obj = trackhubs.models.Genome(
            name=genome_dict['genome'],
            trackdb_location=genome_dict['trackDb'],
            hub=hub
        )
        new_genome_obj.save()
        return new_genome_obj


def save_assembly(assembly_dict, genome):
    """
    Save the assembly in MySQL DB if it doesn't exist already
    :param assembly_dict: assembly dictionary containing all the parsed info
    :param genome: genome object associated with this assembly
    :returns: either the existing assembly or the new created one
    """
    existing_assembly_obj = trackhubs.models.Assembly.objects.filter(name=assembly_dict['name']).first()
    if existing_assembly_obj:
        return existing_assembly_obj
    else:
        new_assembly_obj = trackhubs.models.Assembly(
            accession='accession_goes_here',
            name=assembly_dict['name'],
            long_name='',
            synonyms='',
            genome=genome
        )
        new_assembly_obj.save()
        return new_assembly_obj


def save_trackdb(url, hub, genome, assembly):
    """
    Save the genome in MySQL DB  if it doesn't exist already
    :param url: trackdb url
    :param hub: hub object associated with this trackdb
    :param genome: genome object associated with this trackdb
    :param assembly: assembly object associated with this trackdb
    :returns: either the existing trackdb or the new created one
    """
    existing_trackdb_obj = trackhubs.models.Trackdb.objects.filter(source_url=url).first()
    if existing_trackdb_obj:
        trackdb_obj = existing_trackdb_obj
    else:
        trackdb_obj = trackhubs.models.Trackdb(
            public=True,
            created=int(time.time()),
            updated=int(time.time()),
            assembly=assembly,
            hub=hub,
            genome=genome,
            source_url=url
        )
        trackdb_obj.save()

    return trackdb_obj


def save_track(track_dict, trackdb, file_type, visibility):
    """
    Save the track in MySQL DB  if it doesn't exist already
    :param track_dict: track dictionary containing all the parsed info
    :param trackdb: trackdb object associated with this track
    :param file_type: file type string associated with this track
    :param visibility: visibility string associated with this track (default: 'hide')
    :returns: either the existing track or the new created one
    """
    existing_track_obj = None
    try:
        existing_track_obj = trackhubs.models.Track.objects.filter(big_data_url=track_dict['bigDataUrl']).first()
    except KeyError:
        logger.info("bigDataUrl doesn't exist for track: {}".format(track_dict['track']))

    if existing_track_obj:
        return existing_track_obj
    else:
        new_track_obj = trackhubs.models.Track(
            # save name only without 'on' or 'off' settings
            name=get_first_word(track_dict['track']),
            short_label=track_dict.get('shortLabel'),
            long_label=track_dict.get('longLabel'),
            big_data_url=track_dict.get('bigDataUrl'),
            html=track_dict.get('html'),
            parent=None,  # track
            trackdb=trackdb,
            file_type=trackhubs.models.FileType.objects.filter(name=file_type).first(),
            visibility=trackhubs.models.Visibility.objects.filter(name=visibility).first()
        )
        new_track_obj.save()
        return new_track_obj


def get_first_word(tabbed_info):
    """
    Get the first word in a sentence, this is useful when
    we want to get file type, for instance,
    >> get_first_word('bigBed 6 +') will return 'bigBed'
    :param tabbed_info: the string (e.g. 'bigBed 6 +')
    :returns: the first word in the string
    """
    return tabbed_info.rstrip('\n').split(' ')[0]  # e.g ['bigBed', '6', '+']


def add_parent_id(parent_name, current_track):
    """
    Update track's parent id if there is any
    :param parent_name: extracted from the track info
    :param current_track: current track object
    """
    # get the track parent name only without extra configuration
    # e.g. 'uniformDnasePeaks off' becomes 'uniformDnasePeaks'
    parent_name_only = get_first_word(parent_name).strip()
    # IDEA: DRY create get where function
    parent_track = trackhubs.models.Track.objects.filter(name=parent_name_only).first()
    current_track.parent_id = parent_track.track_id
    current_track.save()
    return parent_track


def get_parents(track):
    """
    Get parent and grandparent (if any) of a given track
    :param track: track object
    :returns: the parent and grandparent (if any)
    """

    try:
        parent_track_id = track.parent_id
        parent_track = trackhubs.models.Track.objects.filter(track_id=parent_track_id).first()
    except AttributeError:
        logger.error("Couldn't get the parent of {}".format(track.name))

    try:
        grandparent_track_id = parent_track.parent_id
        grandparent_track = trackhubs.models.Track.objects.filter(track_id=grandparent_track_id).first()
    except AttributeError:
        grandparent_track = None

    return parent_track, grandparent_track


def is_hub_exists(hub_url):
    existing_hub_obj = trackhubs.models.Hub.objects.filter(url=hub_url).first()
    if existing_hub_obj:
        return True
    return False


def save_and_update_document(hub_url, data_type, current_user):
    """
    Save everything in MySQL DB then Elasticsearch and
    update both after constructing the required objects
    :param hub_url: the hub url provided by the submitter
    :param data_type: the data type provided by the user (if any, default is 'genomics')
    :param current_user: the submitter (current user) id
    :returns: the hub information if the submission was successful otherwise it returns an error
    """
    base_url = hub_url[:hub_url.rfind('/')]
    save_fake_species()

    # TODO: this three lines should be moved somewhere else where they are executed only once
    save_datatype_filetype_visibility(DATA_TYPES, trackhubs.models.DataType)
    save_datatype_filetype_visibility(FILE_TYPES, trackhubs.models.FileType)
    save_datatype_filetype_visibility(VISIBILITY, trackhubs.models.Visibility)

    # Verification step
    # Before we submit the hub we make sure that it doesn't exist already
    if is_hub_exists(hub_url):
        original_owner_id = trackhubs.models.Hub.objects.filter(url=hub_url).first().owner_id
        if original_owner_id == current_user.id:
            return {'error': 'The Hub is already submitted, please delete it before resubmitting it again'}
        original_owner_email = User.objects.filter(id=original_owner_id).first().email
        return {"error": "This hub is already submitted by a different user (the original submitter's email: {})".format(original_owner_email)}

    hub_info_array = parse_file_from_url(hub_url, is_hub=True)

    if hub_info_array:
        hub_info = hub_info_array[0]
        logger.debug("hub_info: {}".format(json.dumps(hub_info, indent=4)))

        # check if the user provides the data type, default is 'genomics'
        if data_type:
            data_type = data_type.lower()
            if data_type not in DATA_TYPES:
                return {"Error": "'{}' isn't a valid data type, the valid ones are: '{}'".format(data_type, ", ".join(DATA_TYPES))}
        else:
            data_type = 'genomics'

        hub_obj = save_hub(hub_info, data_type, current_user)

        genomes_trackdbs_info = parse_file_from_url(base_url + '/' + hub_info['genomesFile'], is_genome=True)
        logger.debug("genomes_trackdbs_info: {}".format(json.dumps(genomes_trackdbs_info, indent=4)))

        for genomes_trackdb in genomes_trackdbs_info:
            # logger.debug("genomes_trackdb: {}".format(json.dumps(genomes_trackdb, indent=4)))

            genome_obj = save_genome(genomes_trackdb, hub_obj)

            assembly_info = {'name': genomes_trackdb['genome']}
            assembly_obj = save_assembly(assembly_info, genome_obj)

            # Save the initial data
            trackdb_obj = save_trackdb(base_url + '/' + genomes_trackdb['trackDb'], hub_obj, genome_obj, assembly_obj)

            trackdbs_info = parse_file_from_url(base_url + '/' + genomes_trackdb['trackDb'], is_trackdb=True)
            # logger.debug("trackdbs_info: {}".format(json.dumps(trackdbs_info, indent=4)))

            trackdb_data = []
            trackdb_configuration = {}
            for track in trackdbs_info:
                # logger.debug("track: {}".format(json.dumps(track, indent=4)))

                if 'track' in track:
                    # default value
                    visibility = 'hide'
                    # get the file type and visibility
                    # TODO: if file_type in FILE_TYPES Good, Else Error
                    if 'type' in track:
                        file_type = get_datatype_filetype_visibility(track['type'], trackhubs.models.FileType, file_type=True).name
                    if 'visibility' in track:
                        visibility = get_datatype_filetype_visibility(track['visibility'], trackhubs.models.Visibility).name

                    track_obj = get_obj_if_exist(track['track'], trackhubs.models.Track)
                    if not track_obj:
                        track_obj = save_track(track, trackdb_obj, file_type, visibility)

                    trackdb_data.append(
                        {
                            'id': track_obj.name,
                            'name': track_obj.long_label
                        }
                    )

                    # if the track is parent we prepare the configuration object
                    if any(k in track for k in ('compositeTrack', 'superTrack', 'container')):
                        # logger.debug("'{}' is parent".format(track['track']))
                        trackdb_configuration[track['track']] = track
                        trackdb_configuration[track['track']].pop('url', None)

                    # if the track is a child, add the parent id and update
                    # the configuration to include the current track
                    if 'parent' in track:
                        add_parent_id(track['parent'], track_obj)
                        parent_track_obj, grandparent_track_obj = get_parents(track_obj)

                        if grandparent_track_obj is None:  # Then we are in the first level (subtrack)
                            if 'members' not in trackdb_configuration[parent_track_obj.name]:
                                trackdb_configuration[parent_track_obj.name].update({
                                    'members': {
                                        track['track']: track
                                    }
                                })
                            else:
                                trackdb_configuration[parent_track_obj.name]['members'].update({
                                    track['track']: track
                                })

                        else:  # we are in the second level (subsubtrack)
                            if 'members' not in trackdb_configuration[grandparent_track_obj.name]['members'][parent_track_obj.name]:
                                trackdb_configuration[grandparent_track_obj.name]['members'][parent_track_obj.name].update({
                                    'members': {
                                        track['track']: track
                                    }
                                })
                            else:
                                trackdb_configuration[grandparent_track_obj.name]['members'][parent_track_obj.name]['members'].update({
                                    track['track']: track
                                })

            # update MySQL
            current_trackdb = Trackdb.objects.get(trackdb_id=trackdb_obj.trackdb_id)
            current_trackdb.configuration = trackdb_configuration
            current_trackdb.data = trackdb_data
            current_trackdb.save()
            # Update Elasticsearch trackdb document
            trackdb_obj.update_trackdb_document(file_type, trackdb_data, trackdb_configuration, hub_obj)

        return {'success': 'The hub is submitted successfully'}

    return None


# TODO: add delete_hub() etc
