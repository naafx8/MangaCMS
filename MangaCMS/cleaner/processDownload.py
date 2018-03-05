

# Ideally, all downloaded archives should run through this function.
import traceback
import os.path
import hashlib
import settings
import runStatus
import deduplicator.archChecker
import MangaCMS.ScrapePlugins.MangaScraperDbBase
import MangaCMS.cleaner.archCleaner as ac
import UploadPlugins.Madokami.uploader as up

PHASH_DISTANCE = 4


NEGATIVE_KEYWORDS = [
	'www.hentairules.com',     # HentaiRules seems to consistently bundle lots of shit into a single archive, which
	                           # then gets deduped against, and you wind up with 37 one-shots in a single file,
	                           # which then makes the tags less useful.
]


class DownloadProcessor(MangaCMS.ScrapePlugins.MangaScraperDbBase.MangaScraperDbBase):

	plugin_name = 'Download Processor'

	logger_path = 'Main.DlProc'
	plugin_key  = None
	plugin_type = 'Utility'

	def _create_or_update_file_entry_path(self, oldPath, newPath, setDeleted=False, setDuplicate=False, setPhash=False, reuse_sess=None):
		oldItemRoot, oldItemFile = os.path.split(oldPath)
		newItemRoot, newItemFile = os.path.split(newPath)

		assert oldPath != newPath

		with self.db.session_context(reuse_sess=reuse_sess) as sess:
			old_row = sess.query(self.db.ReleaseFile)                \
				.filter(self.db.ReleaseFile.dirpath == oldItemRoot)  \
				.filter(self.db.ReleaseFile.filename == oldItemFile) \
				.scalar()

			new_row = sess.query(self.db.ReleaseFile)                \
				.filter(self.db.ReleaseFile.dirpath == newItemRoot)  \
				.filter(self.db.ReleaseFile.filename == newItemFile) \
				.scalar()

			if not new_row:
				hash_md5 = hashlib.md5()
				with open(newPath, "rb") as f:
					hash_md5.update(f.read())
				fhash = hash_md5.hexdigest()

				# Use an existing file row (if present), via the md5sum
				new_row = sess.query(self.db.ReleaseFile)          \
					.filter(self.db.ReleaseFile.fhash == fhash) \
					.scalar()

				if new_row:
					self.log.info("Have existing row for fhash!")

				# But only if the existing file actually exists.
				if new_row and not os.path.exists(os.path.join(new_row.dirpath, new_row.filename)):
					self.log.warning("Existing row for hash exists, but path is not valid (%s, %s)!",
						newItemRoot,  newItemFile)

					assert(new_row.fhash == fhash)
					# Since a appropriate row exists but the paths aren't valid, just point that
					# row at the file on-disk.
					new_row.dirpath  = newItemRoot
					new_row.filename = newItemFile

				else:
					new_row = self.db.ReleaseFile(
							dirpath  = newItemRoot,
							filename = newItemFile,
							fhash    = fhash
						)

					sess.add(new_row)
					sess.flush()

			if not old_row:
				self.log.warning("Trying to update file path where the file doesn't exist!")
				self.log.warning("Dir path: '%s', fname: '%s'", oldItemRoot, oldItemFile)
				return

			releases = old_row.manga_releases + old_row.hentai_releases

			# Copy over the tags.
			for m_tag in old_row.manga_tags:
				new_row.manga_tags.add(m_tag)

			for h_tag in old_row.hentai_tags:
				new_row.hentai_tags.add(h_tag)

			# And then delete the old row (but only if it's changed,
			# since we might have matched against it by md5sum).
			if old_row.id != new_row.id:
				sess.delete(old_row)
			else:
				self.log.warning("Old row matches new row by md5sum. Not deleting old row.")
			# This flush seems to be required. Somehow.
			sess.flush()

			# Re-point any items that point to the old file to the new file
			for release in releases:
				self.log.info("Re-pointing release %s to new file (%s->%s), (%s->%s)", release.id,
					oldPath, newPath,
					release.fileid, new_row.id)

				self.log.info("New row: %s, new_row id: %s", new_row, new_row.id)
				release.fileid = new_row.id
				assert release.fileid

				# And set any flag(s) on the entries that pointed to the old files.
				if setDeleted:
					release.deleted = setDeleted
				if setDuplicate:
					release.was_duplicate = setDuplicate
				if setPhash:
					release.phash_duplicate = setPhash


	def _crossLink(self, delItem, dupItem, isPhash=False):
		self.log.warning("Duplicate found! Cross-referencing file")
		self._create_or_update_file_entry_path(delItem, dupItem, setDeleted=True, setPhash=isPhash)


	def processDownload(self,
				seriesName,
				archivePath,
				pathPositiveFilter = None,
				crossReference     = True,
				doUpload           = True,
				**kwargs
			):

		if self.mon_con:
			self.mon_con.incr('processed-download', 1)

		if 'phashThresh' in kwargs:
			phashThreshIn = kwargs.pop('phashThresh')
			self.log.warn("Phash search distance overridden!")
			self.log.warn("Search distance = %s", phashThreshIn)
			for line in traceback.format_stack():
				self.log.warn(line.rstrip())

		else:
			phashThreshIn = PHASH_DISTANCE
			self.log.info("Phash search distance = %s", phashThreshIn)

		if 'dedupMove' in kwargs:
			moveToPath = kwargs.pop('dedupMove')
		else:
			moveToPath = False



		if moveToPath:
			retTags = ""
		else:
			archCleaner = MangaCMS.cleaner.archCleaner.ArchCleaner()
			try:
				retTags, archivePath_updated = archCleaner.processNewArchive(archivePath, **kwargs)
				if archivePath_updated != archivePath:
					self._create_or_update_file_entry_path(archivePath, archivePath_updated)
					archivePath = archivePath_updated

			except Exception:
				self.log.critical("Error processing archive '%s'", archivePath)
				self.log.critical(traceback.format_exc())
				retTags = "corrupt unprocessable"
				self.mon_con.incr('corrupt-archive', 1)


		with self.db.session_context() as sess:

			# Limit dedup matches to the served directories.
			if not pathPositiveFilter:
				self.log.info("Using manga download folders for path filtering.")
				pathPositiveFilter = [item['dir'] for item in settings.mangaFolders.values()]

			# Let the remote deduper do it's thing.
			# It will delete duplicates automatically.

			phashThresh = phashThreshIn

			while True:
				dc = deduplicator.archChecker.ArchChecker(archivePath, phashDistance=phashThresh, pathPositiveFilter=pathPositiveFilter, lock=False)
				retTagsTmp, bestMatch, intersections = dc.process(moveToPath=moveToPath)

				if 'deleted' in retTagsTmp:
					self.mon_con.incr('deleted-archive', 1)
					break
				if phashThresh == 0:
					self.mon_con.incr('phash-exhausted', 1)
					break
				if not 'phash-conflict' in retTagsTmp:
					break
				if phashThresh < phashThreshIn:
					self.mon_con.incr('phash-thresh-reduced', 1)
					retTagsTmp += " phash-thresh-reduced phash-thresh-%s" % phashThresh
				phashThresh = phashThresh - 1
				self.log.warning("Phash conflict! Reducing search threshold to %s to try to work around.", phashThresh)

			retTags += " " + retTagsTmp
			retTags = retTags.strip()

			if "phash-duplicate" in retTags:
				self.mon_con.incr('phash-duplicate', 1)

			elif 'deleted' in retTags:
				self.mon_con.incr('binary-duplicate', 1)

			if bestMatch and crossReference:
				isPhash = False
				if "phash-duplicate" in retTags:
					isPhash = True

				self._crossLink(archivePath, bestMatch, isPhash=isPhash)


			# processNewArchive returns "damaged" or "duplicate" for the corresponding archive states.
			# Since we don't want to upload archives that are either, we skip if retTags is anything other then ""
			# Also, don't upload porn
			if self.is_manga and (not retTags or retTags=="fewfiles") and seriesName and doUpload:
				try:
					self.log.info("Trying to upload file '%s'.", archivePath)
					up.uploadFile(seriesName, archivePath)
					retTags += " uploaded"
					self.mon_con.incr('uploaded', 1)
				except ConnectionRefusedError:
					self.log.warning("Uploading file failed! Connection Refused!")
					for line in traceback.format_exc().split("\n"):
						self.log.error("	%s", line)
				except Exception:
					self.log.error("Uploading file failed! Unknown Error!")
					for line in traceback.format_exc().split("\n"):
						self.log.error("	%s", line)
			else:
				self.log.info("File not slated for upload: '%s' (tags: '%s')", archivePath, retTags)

			if retTags:
				self.log.info("Applying tags to archive: '%s'", retTags)
			if "deleted" in retTags:
				self.log.warning("Item was deleted!")
		return retTags.strip()


# Subclasses to specify the right table names
class MangaProcessor(DownloadProcessor):
	tableName = 'MangaItems'
	is_manga = True

	def __init__(self, *args, **kwargs):
		self.logger_path += "-" + self.tableName
		super().__init__(*args, **kwargs)

class HentaiProcessor(DownloadProcessor):
	tableName = 'HentaiItems'
	is_manga = False

	def __init__(self, *args, **kwargs):
		self.logger_path += "-" + self.tableName
		super().__init__(*args, **kwargs)

def processDownload(*args, **kwargs):
	if 'pron' in kwargs:
		isPron = kwargs.pop('pron')
	else:
		isPron = False

	if isPron:
		dlProc = HentaiProcessor()
	else:
		dlProc = MangaProcessor()

	return dlProc.processDownload(*args, **kwargs)

def dedupItem(itemPath, rmPath):
	dlProc = MangaProcessor()
	dlProc.processDownload(seriesName=None, archivePath=itemPath, dedupMove=rmPath, deleteDups=True, includePHash=True)


if __name__ == "__main__":

	import MangaCMS.lib.logSetup
	MangaCMS.lib.logSetup.initLogging()

	import sys

	if len(sys.argv) > 1:
		processDownload(seriesName=None, archivePath=[sys.argv[1]])

