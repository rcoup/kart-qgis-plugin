import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.PyQt.QtWidgets import (QDockWidget, QTreeWidgetItem,
                                 QAbstractItemView, QFileDialog, QAction,
                                 QMenu, QInputDialog, QMessageBox)

from qgis.utils import iface
from qgis.core import Qgis

from kart.kartapi import repos, addRepo, Repository, executeskart
from kart.gui.diffviewer import DiffViewerDialog
from kart.gui.historyviewer import HistoryDialog
from kart.gui.conflictsdialog import ConflictsDialog

pluginPath = os.path.split(os.path.dirname(__file__))[0]


def icon(f):
    return QIcon(os.path.join(pluginPath, "img", f))


repoIcon = icon("repository.png")
addRepoIcon = icon("addrepo.png")
createRepoIcon = icon("createrepo.png")
logIcon = icon('log.png')
importIcon = icon('import.png')
checkoutIcon = icon('checkout.png')
commitIcon = icon('commit.png')
discardIcon = icon('reset.png')
layerIcon = icon('layer.png')
mergeIcon = icon("merge.png")
addtoQgisIcon = icon('openinqgis.png')
diffIcon = icon("changes.png")
abortIcon = icon("abort.png")
resolveIcon = icon("resolve.png")

WIDGET, BASE = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), 'dockwidget.ui'))


class KartDockWidget(BASE, WIDGET):
    def __init__(self):
        super(QDockWidget, self).__init__(iface.mainWindow())
        self.setupUi(self)

        pixmap = QPixmap(os.path.join(pluginPath, "img", "kart-logo.png"))
        self.labelHeader.setPixmap(pixmap)
        self.tree.setFocusPolicy(Qt.NoFocus)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.customContextMenuRequested.connect(self.showPopupMenu)

        self.fillTree()

    def fillTree(self):
        self.tree.clear()
        self.reposItem = ReposItem()
        self.tree.addTopLevelItem(self.reposItem)

    def showPopupMenu(self, point):
        item = self.tree.currentItem()
        self.menu = self.createMenu(item)
        point = self.tree.mapToGlobal(point)
        self.menu.popup(point)

    def createMenu(self, item):
        def _f(f, *args):
            def wrapper():
                f(*args)
            return wrapper

        menu = QMenu()
        for text in item.actions():
            func, icon = item.actions()[text]
            action = QAction(icon, text, menu)
            action.triggered.connect(_f(func))
            menu.addAction(action)

        return menu


class RefreshableItem(QTreeWidgetItem):
    def refreshContent(self):
        self.takeChildren()
        self.populate()


class ReposItem(RefreshableItem):
    def __init__(self):
        QTreeWidgetItem.__init__(self)

        self.setText(0, "Repositories")
        self.setIcon(0, repoIcon)

        self.populate()

    def populate(self):
        for repo in repos():
            item = RepoItem(repo)
            self.addChild(item)

    def actions(self):
        actions = {
            "Add existing repository...": (self.addRepo, addRepoIcon),
            "Create new repository...": (self.createRepo, createRepoIcon)
        }

        return actions

    def addRepo(self):
        folder = QFileDialog.getExistingDirectory(iface.mainWindow(),
                                                  "Repository Folder", "")
        if folder:
            repo = Repository(folder)
            if repo.isInitialized():
                item = RepoItem(repo)
                self.addChild(item)
                addRepo(repo)
            else:
                iface.messageBar().pushMessage(
                    "Error",
                    "The selected folder is not a Kart repository",
                    level=Qgis.Warning)

    @executeskart
    def createRepo(self):
        folder = QFileDialog.getExistingDirectory(iface.mainWindow(),
                                                  "Repository Folder", "")
        if folder:
            repo = Repository(folder)
            repo.init()
            if repo.isInitialized():
                item = RepoItem(repo)
                self.addChild(item)
            else:
                iface.messageBar().pushMessage(
                    "Error",
                    "Could not initialize repository",
                    level=Qgis.Warning)


class RepoItem(RefreshableItem):
    def __init__(self, repo):
        QTreeWidgetItem.__init__(self)
        self.repo = repo

        self.setText(0, repo.path)
        self.setIcon(0, repoIcon)

        self.populate()

    def populate(self):
        self.layersItem = LayersItem(self.repo)
        self.addChild(self.layersItem)

    def actions(self):
        actions = {
        }
        if self.repo.isMerging():
            actions.update({
                "Resolve conflicts...": (self.resolveConflicts, resolveIcon),
                "Continue merge": (self.continueMerge, mergeIcon),
                "Abort merge": (self.abortMerge, abortIcon)
                })
        else:
            actions.update({
                "Show log...": (self.showLog, logIcon),
                "Show working tree changes...": (self.showChanges, diffIcon),
                "Discard working tree changes": (self.discardChanges, discardIcon),
                "Commit working tree changes...": (self.commitChanges, commitIcon),
                "Switch branch...": (self.switchBranch, checkoutIcon),
                "Merge into current branch...": (self.mergeBranch, mergeIcon),
                "Import layer into repo...": (self.importLayer, importIcon)
                })

        return actions

    @executeskart
    def showLog(self):
        dialog = HistoryDialog(self.repo)
        dialog.exec()

    @executeskart
    def importLayer(self):
        filename, _ = QFileDialog.getOpenFileName(
            iface.mainWindow(), "Select GPKG file to import", "", "*.gpkg")
        if filename:
            self.repo.importGpkg(filename)
            iface.messageBar().pushMessage("Import",
                                           "Layer correctly imported",
                                           level=Qgis.Info)
            self.layersItem.refresh()

    @executeskart
    def commitChanges(self):
        if self.repo.isMerging():
            iface.messageBar().pushMessage("Commit",
                                           "Cannot commit if repository while repository is in merging status",
                                           level=Qgis.Warning)
        elif self.repo.isWorkingTreeClean():
            iface.messageBar().pushMessage("Commit",
                                           "Nothing to commit",
                                           level=Qgis.Warning)
        else:
            msg, ok = QInputDialog.getMultiLineText(iface.mainWindow(),
                                                    'Commit',
                                                    'Enter commit message:')
            if ok and msg:
                self.repo.commit(msg)
                iface.messageBar().pushMessage("Commit",
                                               "Changes correctly committed",
                                               level=Qgis.Info)

    @executeskart
    def showChanges(self):
        changes = self.repo.diff()
        hasChanges = any([bool(layerchanges) for layerchanges in changes.values()])
        if hasChanges:
            dialog = DiffViewerDialog(iface.mainWindow(), changes)
            dialog.exec()
        else:
            iface.messageBar().pushMessage("Changes",
                                           "There are no changes in the working tree",
                                           level=Qgis.Warning)

    @executeskart
    def switchBranch(self):
        branches = self.repo.branches()
        branch, ok = QInputDialog.getItem(iface.mainWindow(),
                                          "Branch",
                                          "Select branch to switch to:",
                                          branches,
                                          editable=False)
        if ok:
            self.repo.checkoutBranch(branch)

    @executeskart
    def mergeBranch(self):
        branches = self.repo.branches()
        branch, ok = QInputDialog.getItem(
            iface.mainWindow(),
            "Branch",
            "Select branch to merge into current branch:",
            branches,
            editable=False)
        if ok:
            conflicts = self.repo.mergeBranch(branch)
            if conflicts:
                QMessageBox.warning(iface.mainWindow(), "Merge",
                                    "There were conflicts during the merge operation.\n"
                                    "Resolve them and then commit your changes to \n"
                                    "complete the merge.")
            else:
                iface.messageBar().pushMessage("Merge",
                                               "Branch correctly merged",
                                               level=Qgis.Info)

    @executeskart
    def discardChanges(self):
        self.repo.restore("HEAD")
        iface.messageBar().pushMessage("Discard changes",
                                       "Working tree changes have been discarded",
                                       level=Qgis.Info)

    @executeskart
    def continueMerge(self):
        if self.repo.conflicts():
            iface.messageBar().pushMessage("Merge",
                                           "Cannot continue. There are merge conflicts.",
                                           level=Qgis.Warning)
        else:
            self.repo.continueMerge()
            iface.messageBar().pushMessage("Merge",
                                       "Merge operation was correctly continued and closed",
                                       level=Qgis.Info)

    @executeskart
    def abortMerge(self):
        self.repo.abortMerge()
        iface.messageBar().pushMessage("Merge",
                                       "Merge operation was correctly aborted",
                                       level=Qgis.Info)

    @executeskart
    def resolveConflicts(self):
        conflicts = self.repo.conflicts()
        if conflicts:
            dialog = ConflictsDialog(conflicts)
            dialog.exec()
            if dialog.okToMerge:
                self.repo.resolveConflicts(dialog.resolvedFeatures)
                self.repo.continueMerge()
                iface.messageBar().pushMessage("Merge",
                                           "Merge operation was correctly continued and closed",
                                           level=Qgis.Info)
        else:
            iface.messageBar().pushMessage("Resolve",
                                       "There are no conflicts to resolve",
                                       level=Qgis.Warning)


class LayersItem(RefreshableItem):
    def __init__(self, repo):
        QTreeWidgetItem.__init__(self)

        self.repo = repo

        self.setText(0, "Layers")
        self.setIcon(0, layerIcon)

        self.populate()

    def populate(self):
        layers = self.repo.layers()
        for layer in layers:
            item = LayerItem(layer, self.repo)
            self.addChild(item)

    def actions(self):
        return {}


class LayerItem(QTreeWidgetItem):
    def __init__(self, layername, repo):
        QTreeWidgetItem.__init__(self)
        self.layername = layername
        self.repo = repo

        self.setText(0, layername)
        self.setIcon(0, layerIcon)

    def actions(self):
        actions = {
            "Add to QGIS project": (self.addToProject, addtoQgisIcon)
        }

        if not self.repo.isMerging():
            actions.update({
                "Commit working tree changes...": (self.commitChanges, commitIcon)
            })

        return actions

    def addToProject(self):
        name = os.path.basename(self.repo.path)
        path = os.path.join(self.repo.path,
                            f"{name}.gpkg|layername={self.layername}")
        iface.addVectorLayer(path, self.layername, "ogr")


    @executeskart
    def commitChanges(self):
        if self.repo.isMerging():
            iface.messageBar().pushMessage("Commit",
                                           "Cannot commit if repository while repository is in merging status",
                                           level=Qgis.Warning)
        else:
            changes = self.repo.changes().get(self.layername, {})
            if changes:
                msg, ok = QInputDialog.getMultiLineText(iface.mainWindow(),
                                                        'Commit',
                                                        'Enter commit message:')
                if ok and msg:
                    self.repo.commit(msg)
                    iface.messageBar().pushMessage("Commit",
                                                   "Changes correctly committed",
                                                   level=Qgis.Info)
            else:
                iface.messageBar().pushMessage("Commit",
                                           "Nothing to commit",
                                           level=Qgis.Warning)