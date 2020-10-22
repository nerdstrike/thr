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

from django.core.management.base import BaseCommand, CommandError
from elasticsearch_dsl import connections

from trackhubs.parser import *


# This file will be edited later
class Command(BaseCommand):
    help = 'Enrich elasticsearch index based on the data stored in MySQL DB.'

    def _enrich(self):
        pass

    def handle(self, *args, **options):
        # Consider when the index doesn't exist
        # self._enrich()
        self.stdout.write(self.style.SUCCESS('Successfully updated the index'))

