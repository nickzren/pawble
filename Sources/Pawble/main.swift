import AppKit
import Foundation
import ImageIO

struct CodexPetProfile {
    let id: String
    let displayName: String
    let description: String?
    let spritesheetPath: String
}

struct PawbleRuntimeConfig: Decodable {
    let schemaVersion: Int
    let idleFrameSequence: [Int]?
    let movementFrameSource: String?
    let mirrorMovementFrameSourceForLeft: Bool?

    static let empty = PawbleRuntimeConfig(
        schemaVersion: 1,
        idleFrameSequence: nil,
        movementFrameSource: nil,
        mirrorMovementFrameSourceForLeft: nil
    )
}

enum CodexPetState: String, CaseIterable, Hashable {
    case idle
    case runningRight = "running-right"
    case runningLeft = "running-left"
    case waving
    case jumping
    case failed
    case waiting
    case running
    case review

    var row: Int {
        switch self {
        case .idle: return 0
        case .runningRight: return 1
        case .runningLeft: return 2
        case .waving: return 3
        case .jumping: return 4
        case .failed: return 5
        case .waiting: return 6
        case .running: return 7
        case .review: return 8
        }
    }

    var frameCount: Int {
        switch self {
        case .idle: return 6
        case .runningRight: return 8
        case .runningLeft: return 8
        case .waving: return 4
        case .jumping: return 5
        case .failed: return 8
        case .waiting: return 6
        case .running: return 6
        case .review: return 6
        }
    }

    var frameInterval: TimeInterval {
        switch self {
        case .runningRight, .runningLeft, .running:
            return 0.12
        case .jumping:
            return 0.16
        case .waving:
            return 0.22
        case .failed, .waiting, .review:
            return 0.35
        case .idle:
            return 0.8
        }
    }

    var durationMilliseconds: Int {
        switch self {
        case .runningRight, .runningLeft:
            return Int.random(in: 6000...9000)
        case .running:
            return 3000
        case .jumping:
            return 1800
        case .waving:
            return 2200
        case .failed:
            return 3600
        case .waiting, .review:
            return 4500
        case .idle:
            return 5000
        }
    }
}

struct CodexPetPack {
    static let columns = 8
    static let rows = 9
    static let cellWidth = 192
    static let cellHeight = 208
    static let atlasWidth = columns * cellWidth
    static let atlasHeight = rows * cellHeight

    let url: URL
    let profile: CodexPetProfile
    let runtimeConfig: PawbleRuntimeConfig
    let frames: [CodexPetState: [NSImage]]
    let movementRightFrames: [NSImage]
    let movementLeftFrames: [NSImage]

    static func load(from url: URL) throws -> CodexPetPack {
        try validateDirectory(url)

        let profileURL = url.appendingPathComponent("pet.json")
        guard FileManager.default.fileExists(atPath: profileURL.path) else {
            throw PawbleError.validation(["pet.json: missing required Codex pet metadata"])
        }

        let profile = try loadProfile(from: profileURL)
        let runtimeConfig = try loadRuntimeConfig(from: url)
        let spritesheetURL = try resolvedSpritesheetURL(profile.spritesheetPath, packURL: url)
        let sheet = try loadSpritesheet(spritesheetURL)

        var frames: [CodexPetState: [NSImage]] = [:]
        for state in CodexPetState.allCases {
            frames[state] = try cropFrames(for: state, from: sheet)
        }

        let movementSource = runtimeConfig.movementFrameSource.flatMap(CodexPetState.init(rawValue:))
        let sourceFrames = movementSource.flatMap { frames[$0] } ?? []
        let movementRightFrames = sourceFrames.nonEmpty ?? frames[.runningRight] ?? []
        let movementLeftFrames: [NSImage]
        if runtimeConfig.mirrorMovementFrameSourceForLeft == true, !sourceFrames.isEmpty {
            movementLeftFrames = sourceFrames.map { $0.horizontallyFlipped() }
        } else {
            movementLeftFrames = frames[.runningLeft] ?? []
        }

        return CodexPetPack(
            url: url,
            profile: profile,
            runtimeConfig: runtimeConfig,
            frames: frames,
            movementRightFrames: movementRightFrames,
            movementLeftFrames: movementLeftFrames
        )
    }

    private static func validateDirectory(_ url: URL) throws {
        var isDirectory = ObjCBool(false)
        let exists = FileManager.default.fileExists(atPath: url.path, isDirectory: &isDirectory)
        if !exists {
            throw PawbleError.validation(["\(url.path): pet package directory does not exist"])
        }
        if !isDirectory.boolValue {
            throw PawbleError.validation(["\(url.path): pet package path is not a directory"])
        }
    }

    private static func loadProfile(from url: URL) throws -> CodexPetProfile {
        let data = try Data(contentsOf: url)
        let raw: Any
        do {
            raw = try JSONSerialization.jsonObject(with: data)
        } catch {
            throw PawbleError.validation(["pet.json: invalid JSON: \(error.localizedDescription)"])
        }

        guard let object = raw as? [String: Any] else {
            throw PawbleError.validation(["pet.json: root value must be an object"])
        }

        var issues: [String] = []
        let id = requiredString("id", in: object, issues: &issues)
        let displayName = requiredString("displayName", in: object, issues: &issues)
        let spritesheetPath = requiredString("spritesheetPath", in: object, issues: &issues)
        let description = object["description"] as? String

        if !issues.isEmpty {
            throw PawbleError.validation(issues)
        }

        return CodexPetProfile(
            id: id ?? "",
            displayName: displayName ?? "",
            description: description,
            spritesheetPath: spritesheetPath ?? ""
        )
    }

    private static func requiredString(_ key: String, in object: [String: Any], issues: inout [String]) -> String? {
        guard let value = object[key] as? String, !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            issues.append("pet.json: \(key) must be a non-empty string")
            return nil
        }
        return value
    }

    private static func resolvedSpritesheetURL(_ path: String, packURL: URL) throws -> URL {
        var issues: [String] = []
        if path != "spritesheet.webp" {
            issues.append("pet.json: spritesheetPath must be spritesheet.webp")
        }
        if path.hasPrefix("/") {
            issues.append("pet.json: spritesheetPath must be relative, got absolute path \(path)")
        }
        if path.split(separator: "/").contains("..") {
            issues.append("pet.json: spritesheetPath must not contain '..': \(path)")
        }
        if !issues.isEmpty {
            throw PawbleError.validation(issues)
        }

        let url = packURL.appendingPathComponent(path).standardizedFileURL
        let packPath = packURL.standardizedFileURL.path
        guard url.path.hasPrefix(packPath + "/") else {
            throw PawbleError.validation(["pet.json: spritesheetPath escapes the package"])
        }
        guard FileManager.default.fileExists(atPath: url.path) else {
            throw PawbleError.validation(["\(path): missing spritesheet file"])
        }
        return url
    }

    private static func loadRuntimeConfig(from packURL: URL) throws -> PawbleRuntimeConfig {
        let configURL = packURL.appendingPathComponent("pawble.json")
        guard FileManager.default.fileExists(atPath: configURL.path) else {
            return .empty
        }

        let config = try JSONDecoder().decode(PawbleRuntimeConfig.self, from: Data(contentsOf: configURL))
        var issues: [String] = []

        if config.schemaVersion != 1 {
            issues.append("pawble.json: schemaVersion must be 1")
        }

        if let idleFrameSequence = config.idleFrameSequence {
            if idleFrameSequence.isEmpty {
                issues.append("pawble.json: idleFrameSequence must be a non-empty array")
            }
            for (index, value) in idleFrameSequence.enumerated() where value < 0 || value >= CodexPetState.idle.frameCount {
                issues.append(
                    "pawble.json: idleFrameSequence[\(index)] must be an idle frame index between 0 and \(CodexPetState.idle.frameCount - 1)"
                )
            }
        }

        if let movementFrameSource = config.movementFrameSource,
           CodexPetState(rawValue: movementFrameSource) == nil {
            let values = CodexPetState.allCases.map(\.rawValue).joined(separator: ", ")
            issues.append("pawble.json: movementFrameSource must be one of \(values)")
        }

        if !issues.isEmpty {
            throw PawbleError.validation(issues)
        }
        return config
    }

    private static func loadSpritesheet(_ url: URL) throws -> CGImage {
        guard
            let source = CGImageSourceCreateWithURL(url as CFURL, nil),
            let image = CGImageSourceCreateImageAtIndex(source, 0, nil)
        else {
            throw PawbleError.validation(["\(url.lastPathComponent): could not decode spritesheet"])
        }

        let imageType = (CGImageSourceGetType(source) as String?) ?? "unknown"
        if !imageType.lowercased().contains("webp") {
            throw PawbleError.validation(["\(url.lastPathComponent): spritesheet must be WebP, got \(imageType)"])
        }

        if image.width != atlasWidth || image.height != atlasHeight {
            throw PawbleError.validation([
                "\(url.lastPathComponent): spritesheet must be \(atlasWidth)x\(atlasHeight), got \(image.width)x\(image.height)"
            ])
        }

        return image
    }

    private static func cropFrames(for state: CodexPetState, from sheet: CGImage) throws -> [NSImage] {
        try (0..<state.frameCount).map { column in
            let rect = CGRect(
                x: column * cellWidth,
                y: state.row * cellHeight,
                width: cellWidth,
                height: cellHeight
            )
            guard let frame = sheet.cropping(to: rect) else {
                throw PawbleError.validation(["\(state.rawValue)[\(column)]: could not crop frame"])
            }
            return NSImage(cgImage: frame, size: NSSize(width: cellWidth, height: cellHeight))
        }
    }
}

enum PawbleError: LocalizedError {
    case validation([String])

    var errorDescription: String? {
        switch self {
        case .validation(let issues):
            return "Invalid Codex pet package:\n" + issues.map { "- \($0)" }.joined(separator: "\n")
        }
    }
}

final class PawbleAppDelegate: NSObject, NSApplicationDelegate {
    private let loadedPack: CodexPetPack
    private var pack: CodexPetPack?
    private var statusItem: NSStatusItem?
    private var panel: NSPanel?
    private var imageView: NSImageView?
    private var movementTimer: Timer?
    private var frameTimer: Timer?
    private var behaviorTimer: Timer?
    private var lifeTimer: Timer?
    private var currentState = CodexPetState.idle
    private var frameIndex = 0
    private var hasRunSinceLaunch = false
    private var paused = false
    private var tuckedAway = false
    private var dragging = false
    private var userPlacedY: CGFloat?
    private var energy = 0.75
    private var curiosity = 0.45
    private var boredom = 0.10
    private var affection = 0.25
    private var lastCursorReaction = Date.distantPast
    private let displayHeight: CGFloat = 122
    private let edgePadding: CGFloat = 20
    private let lowEnergyThreshold = 0.18
    private let cursorReactionCooldown: TimeInterval = 12
    private let cursorReactionChance = 0.35
    private let cursorJumpDistance: CGFloat = 80
    private let cursorWaveDistance: CGFloat = 190
    private let cursorFollowDistance: CGFloat = 360
    private let cursorFollowChance = 0.30
    private let cursorFollowMinEnergy = 0.55

    init(pack: CodexPetPack) {
        self.loadedPack = pack
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        pack = loadedPack
        configureStatusItem()
        configureWindow()
        placeAtStartingEdge()
        render()
        startTimers()
    }

    func applicationWillTerminate(_ notification: Notification) {
        movementTimer?.invalidate()
        frameTimer?.invalidate()
        behaviorTimer?.invalidate()
        lifeTimer?.invalidate()
    }

    private func configureStatusItem() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let symbol = NSImage(systemSymbolName: "pawprint", accessibilityDescription: "Pawble") {
            item.button?.image = symbol
            item.button?.imagePosition = .imageOnly
        } else {
            item.button?.title = "Pawble"
        }
        statusItem = item
        rebuildMenu()
    }

    private func rebuildMenu() {
        guard let pack else {
            return
        }

        let menu = NSMenu()
        let title = NSMenuItem(title: pack.profile.displayName, action: nil, keyEquivalent: "")
        title.isEnabled = false
        menu.addItem(title)
        menu.addItem(NSMenuItem.separator())

        let pauseItem = NSMenuItem(title: paused ? "Resume" : "Pause", action: #selector(togglePause), keyEquivalent: "")
        pauseItem.target = self
        menu.addItem(pauseItem)

        let tuckItem = NSMenuItem(title: tuckedAway ? "Wake Pet" : "Tuck Away Pet", action: #selector(toggleTuckedAway), keyEquivalent: "")
        tuckItem.target = self
        menu.addItem(tuckItem)

        menu.addItem(NSMenuItem.separator())

        addMenuItem("Run Right", action: #selector(runRight), to: menu)
        addMenuItem("Run Left", action: #selector(runLeft), to: menu)
        addMenuItem("Wave", action: #selector(waving), to: menu)
        addMenuItem("Jump", action: #selector(jumping), to: menu)

        menu.addItem(NSMenuItem.separator())

        addMenuItem("Waiting", action: #selector(waiting), to: menu)
        addMenuItem("Review", action: #selector(review), to: menu)
        addMenuItem("Failed", action: #selector(failed), to: menu)

        menu.addItem(NSMenuItem.separator())

        let quitItem = NSMenuItem(title: "Quit Pawble", action: #selector(quit), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)

        statusItem?.menu = menu
    }

    private func addMenuItem(_ title: String, action: Selector, to menu: NSMenu) {
        let item = NSMenuItem(title: title, action: action, keyEquivalent: "")
        item.target = self
        menu.addItem(item)
    }

    private func configureWindow() {
        let frame = NSRect(origin: .zero, size: panelSize)
        let panel = NSPanel(
            contentRect: frame,
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.level = .floating
        panel.ignoresMouseEvents = false
        panel.hidesOnDeactivate = false
        panel.isReleasedWhenClosed = false
        panel.collectionBehavior = [.canJoinAllSpaces, .transient, .ignoresCycle]

        let imageView = PetOverlayView(frame: NSRect(origin: .zero, size: panelSize))
        imageView.imageScaling = .scaleProportionallyUpOrDown
        imageView.wantsLayer = true
        imageView.layer?.backgroundColor = NSColor.clear.cgColor
        imageView.contextMenuProvider = { [weak self] in
            self?.buildPetContextMenu() ?? NSMenu()
        }
        imageView.dragDidBegin = { [weak self] in
            self?.dragging = true
            self?.rebuildMenu()
        }
        imageView.dragDidEnd = { [weak self] origin in
            guard let self else {
                return
            }
            self.userPlacedY = origin.y
            self.dragging = false
            self.adjustNeeds(energy: -0.03, curiosity: 0.05, boredom: -0.35, affection: 0.20)
            self.currentState = .idle
            self.frameIndex = 0
            self.render()
            self.restartFrameTimer()
            self.scheduleNextBehavior(afterMilliseconds: self.durationMilliseconds(for: self.currentState))
            self.rebuildMenu()
        }
        imageView.clickHandler = { [weak self] in
            self?.petDidClick()
        }
        panel.contentView = imageView

        self.panel = panel
        self.imageView = imageView
    }

    private func buildPetContextMenu() -> NSMenu {
        let menu = NSMenu()
        addMenuItem("Tuck Away", action: #selector(toggleTuckedAway), to: menu)
        return menu
    }

    private func placeAtStartingEdge() {
        guard let panel else {
            return
        }

        let visibleFrame = currentVisibleFrame()
        let startOnLeft = Bool.random()
        let originX = startOnLeft
            ? visibleFrame.minX + edgePadding
            : visibleFrame.maxX - panel.frame.width - edgePadding
        panel.setFrameOrigin(NSPoint(x: originX, y: edgeOriginY(in: visibleFrame)))
        panel.orderFrontRegardless()
    }

    private func startTimers() {
        movementTimer = makeTimer(interval: 0.05, repeats: true) { [weak self] _ in
            self?.tickMovement()
        }
        restartFrameTimer()
        lifeTimer = makeTimer(interval: 1.0, repeats: true) { [weak self] _ in
            self?.tickLife()
        }
        scheduleNextBehavior(afterMilliseconds: durationMilliseconds(for: currentState))
    }

    private func makeTimer(interval: TimeInterval, repeats: Bool, block: @escaping (Timer) -> Void) -> Timer {
        let timer = Timer(timeInterval: interval, repeats: repeats, block: block)
        RunLoop.main.add(timer, forMode: .common)
        return timer
    }

    private func scheduleNextBehavior(afterMilliseconds milliseconds: Int) {
        behaviorTimer?.invalidate()
        let interval = TimeInterval(milliseconds) / 1000.0
        behaviorTimer = makeTimer(interval: interval, repeats: false) { [weak self] _ in
            self?.chooseNextBehavior()
        }
    }

    private func chooseNextBehavior() {
        if paused || tuckedAway || dragging {
            scheduleNextBehavior(afterMilliseconds: 1000)
            return
        }

        let nextState: CodexPetState
        if hasRunSinceLaunch {
            nextState = cursorReactionIfAllowed() ?? behaviorChoices().randomElement() ?? .idle
        } else {
            nextState = Bool.random() ? .runningRight : .runningLeft
            hasRunSinceLaunch = true
        }

        setState(nextState)
        scheduleNextBehavior(afterMilliseconds: durationMilliseconds(for: nextState))
    }

    private func behaviorChoices() -> [CodexPetState] {
        if energy < lowEnergyThreshold {
            return [.waiting, .waiting, .idle, .idle]
        }

        var choices: [CodexPetState] = [.idle, .idle, .idle, .idle]
        if boredom > 0.35 {
            choices += [.waiting, .review, .waving]
        }
        if curiosity > 0.45 {
            choices += [.review, .review, randomRunDirection()]
        }
        if affection > 0.55 {
            choices += [.waving, .jumping]
        }
        if energy > 0.35 {
            choices += [.waving, .jumping]
        }
        if energy > 0.50 {
            choices += [.runningRight, .runningLeft]
        }
        return choices
    }

    private func setState(_ state: CodexPetState) {
        currentState = state
        frameIndex = 0
        applyStateEffects(state)
        render()
        restartFrameTimer()
    }

    private func durationMilliseconds(for state: CodexPetState) -> Int {
        switch state {
        case .idle:
            return Int.random(in: 2500...6500)
        case .runningRight, .runningLeft:
            return Int.random(in: 4500...9000)
        case .waiting, .review:
            return Int.random(in: 2500...5000)
        case .failed:
            return Int.random(in: 2600...4200)
        default:
            return state.durationMilliseconds
        }
    }

    private func restartFrameTimer() {
        frameTimer?.invalidate()
        frameTimer = makeTimer(interval: currentState.frameInterval, repeats: true) { [weak self] _ in
            self?.tickFrame()
        }
    }

    private func tickMovement() {
        guard !paused, !tuckedAway, !dragging, let panel else {
            return
        }
        guard currentState == .runningRight || currentState == .runningLeft else {
            return
        }

        let visibleFrame = currentVisibleFrame()
        var frame = panel.frame
        let direction: CGFloat = currentState == .runningRight ? 1 : -1
        frame.origin.x += direction * 1.2
        frame.origin.y = movementOriginY(in: visibleFrame, frameHeight: frame.height)

        if frame.maxX >= visibleFrame.maxX - edgePadding {
            frame.origin.x = visibleFrame.maxX - frame.width - edgePadding
            setState(.runningLeft)
        } else if frame.minX <= visibleFrame.minX + edgePadding {
            frame.origin.x = visibleFrame.minX + edgePadding
            setState(.runningRight)
        }

        panel.setFrameOrigin(frame.origin)
    }

    private func tickLife() {
        guard !paused, !tuckedAway, !dragging else {
            return
        }

        switch currentState {
        case .runningRight, .runningLeft, .running, .jumping:
            adjustNeeds(energy: -0.04, curiosity: -0.02, boredom: -0.12, affection: 0)
        case .waving:
            adjustNeeds(energy: -0.01, curiosity: -0.01, boredom: -0.10, affection: 0.01)
        case .waiting:
            adjustNeeds(energy: 0.03, curiosity: 0.02, boredom: 0.06, affection: 0)
        case .review:
            adjustNeeds(energy: 0.01, curiosity: -0.10, boredom: -0.04, affection: 0)
        case .failed:
            adjustNeeds(energy: 0.08, curiosity: -0.02, boredom: -0.02, affection: 0)
        case .idle:
            adjustNeeds(energy: 0.03, curiosity: 0.02, boredom: 0.04, affection: -0.005)
        }

        maybeReactToCursor()
    }

    private func maybeReactToCursor() {
        guard currentState == .idle || currentState == .waiting || currentState == .review else {
            return
        }
        guard let reaction = cursorReactionIfAllowed() else {
            return
        }

        setState(reaction)
        scheduleNextBehavior(afterMilliseconds: durationMilliseconds(for: reaction))
    }

    private func cursorReactionIfAllowed() -> CodexPetState? {
        guard Date().timeIntervalSince(lastCursorReaction) > cursorReactionCooldown else {
            return nil
        }
        guard Double.random(in: 0...1) < cursorReactionChance else {
            return nil
        }
        guard let reaction = cursorReactionState() else {
            return nil
        }

        lastCursorReaction = Date()
        return reaction
    }

    private func cursorReactionState() -> CodexPetState? {
        guard !paused, !tuckedAway, !dragging, let panel else {
            return nil
        }

        let mouse = NSEvent.mouseLocation
        let petCenter = NSPoint(x: panel.frame.midX, y: panel.frame.midY)
        let deltaX = mouse.x - petCenter.x
        let deltaY = mouse.y - petCenter.y
        let distance = hypot(deltaX, deltaY)

        if distance < cursorJumpDistance {
            return energy > 0.25 ? .jumping : .waving
        }
        if distance < cursorWaveDistance {
            return .waving
        }
        if
            distance < cursorFollowDistance,
            energy > cursorFollowMinEnergy,
            Double.random(in: 0...1) < cursorFollowChance
        {
            return deltaX >= 0 ? .runningRight : .runningLeft
        }
        return nil
    }

    private func randomRunDirection() -> CodexPetState {
        Bool.random() ? .runningRight : .runningLeft
    }

    private func applyStateEffects(_ state: CodexPetState) {
        switch state {
        case .runningRight, .runningLeft, .running:
            adjustNeeds(energy: -0.08, curiosity: -0.08, boredom: -0.25, affection: 0)
        case .jumping:
            adjustNeeds(energy: -0.08, curiosity: -0.04, boredom: -0.20, affection: 0.03)
        case .waving:
            adjustNeeds(energy: -0.02, curiosity: -0.04, boredom: -0.15, affection: 0.04)
        case .waiting:
            adjustNeeds(energy: 0.02, curiosity: 0.04, boredom: 0.08, affection: 0)
        case .review:
            adjustNeeds(energy: -0.01, curiosity: -0.20, boredom: -0.08, affection: 0)
        case .failed:
            adjustNeeds(energy: 0.12, curiosity: -0.05, boredom: -0.05, affection: 0)
        case .idle:
            adjustNeeds(energy: 0.02, curiosity: 0.01, boredom: 0.02, affection: 0)
        }
    }

    private func adjustNeeds(energy energyDelta: Double, curiosity curiosityDelta: Double, boredom boredomDelta: Double, affection affectionDelta: Double) {
        energy = clampedNeed(energy + energyDelta)
        curiosity = clampedNeed(curiosity + curiosityDelta)
        boredom = clampedNeed(boredom + boredomDelta)
        affection = clampedNeed(affection + affectionDelta)
    }

    private func clampedNeed(_ value: Double) -> Double {
        min(1.0, max(0.0, value))
    }

    private func tickFrame() {
        guard !paused, !tuckedAway else {
            return
        }
        guard frames(for: currentState).count > 1 else {
            return
        }
        frameIndex += 1
        render()
    }

    private func render() {
        guard let imageView else {
            return
        }

        let frames = frames(for: currentState)
        imageView.image = frames.isEmpty ? nil : frames[frameIndex % frames.count]
    }

    private func frames(for state: CodexPetState) -> [NSImage] {
        guard let pack else {
            return []
        }

        switch state {
        case .idle:
            let idleFrames = pack.frames[.idle] ?? []
            if let configuredIdleFrames = configuredFrameSequence(
                pack.runtimeConfig.idleFrameSequence,
                from: idleFrames
            ) {
                return configuredIdleFrames
            }
            return idleFrames
        case .runningRight:
            return pack.movementRightFrames.nonEmpty ?? pack.frames[.runningRight] ?? pack.frames[.idle] ?? []
        case .runningLeft:
            return pack.movementLeftFrames.nonEmpty ?? pack.frames[.runningLeft] ?? pack.frames[.idle] ?? []
        default:
            return pack.frames[state] ?? pack.frames[.idle] ?? []
        }
    }

    private func configuredFrameSequence(_ sequence: [Int]?, from frames: [NSImage]) -> [NSImage]? {
        guard let sequence, !sequence.isEmpty else {
            return nil
        }

        let selectedFrames = sequence.compactMap { index in
            frames.indices.contains(index) ? frames[index] : nil
        }
        return selectedFrames.count == sequence.count ? selectedFrames : nil
    }

    private func currentVisibleFrame() -> NSRect {
        let fallback = NSRect(x: 0, y: 0, width: 1024, height: 768)
        guard let panel else {
            return NSScreen.main?.visibleFrame ?? fallback
        }

        let center = NSPoint(x: panel.frame.midX, y: panel.frame.midY)
        let screen = NSScreen.screens.first { $0.frame.contains(center) } ?? NSScreen.main
        return screen?.visibleFrame ?? fallback
    }

    private var panelSize: NSSize {
        let width = displayHeight * CGFloat(CodexPetPack.cellWidth) / CGFloat(CodexPetPack.cellHeight)
        return NSSize(width: width, height: displayHeight)
    }

    private func edgeOriginY(in visibleFrame: NSRect) -> CGFloat {
        visibleFrame.minY + edgePadding
    }

    private func movementOriginY(in visibleFrame: NSRect, frameHeight: CGFloat) -> CGFloat {
        guard let userPlacedY else {
            return edgeOriginY(in: visibleFrame)
        }

        let minY = visibleFrame.minY + edgePadding
        let maxY = visibleFrame.maxY - frameHeight - edgePadding
        guard maxY >= minY else {
            return minY
        }
        return min(max(userPlacedY, minY), maxY)
    }

    @objc private func togglePause() {
        paused.toggle()
        if paused {
            setState(.idle)
        }
        rebuildMenu()
    }

    @objc private func toggleTuckedAway() {
        tuckedAway.toggle()
        if tuckedAway {
            panel?.orderOut(nil)
        } else {
            panel?.orderFrontRegardless()
        }
        rebuildMenu()
    }

    @objc private func runRight() {
        wakeAndSetState(.runningRight)
    }

    @objc private func runLeft() {
        wakeAndSetState(.runningLeft)
    }

    @objc private func waving() {
        wakeAndSetState(.waving)
    }

    @objc private func jumping() {
        wakeAndSetState(.jumping)
    }

    @objc private func waiting() {
        wakeAndSetState(.waiting)
    }

    @objc private func review() {
        wakeAndSetState(.review)
    }

    @objc private func failed() {
        wakeAndSetState(.failed)
    }

    private func petDidClick() {
        adjustNeeds(energy: -0.02, curiosity: 0.08, boredom: -0.45, affection: 0.25)
        let response: CodexPetState
        if energy > 0.25 {
            response = Bool.random() ? .jumping : .waving
        } else {
            response = .waving
        }
        wakeAndSetState(response)
    }

    private func wakeAndSetState(_ state: CodexPetState) {
        paused = false
        tuckedAway = false
        panel?.orderFrontRegardless()
        setState(state)
        scheduleNextBehavior(afterMilliseconds: durationMilliseconds(for: state))
        rebuildMenu()
    }

    @objc private func quit() {
        NSApp.terminate(nil)
    }
}

final class PetOverlayView: NSImageView {
    var contextMenuProvider: (() -> NSMenu)?
    var dragDidBegin: (() -> Void)?
    var dragDidEnd: ((NSPoint) -> Void)?
    var clickHandler: (() -> Void)?

    override var acceptsFirstResponder: Bool {
        false
    }

    override func hitTest(_ point: NSPoint) -> NSView? {
        guard bounds.contains(point), hasVisiblePixel(at: point) else {
            return nil
        }
        return super.hitTest(point)
    }

    override func rightMouseDown(with event: NSEvent) {
        guard hasVisiblePixel(at: convert(event.locationInWindow, from: nil)) else {
            return
        }
        guard let menu = contextMenuProvider?() else {
            return
        }
        NSMenu.popUpContextMenu(menu, with: event, for: self)
    }

    override func mouseDown(with event: NSEvent) {
        guard hasVisiblePixel(at: convert(event.locationInWindow, from: nil)) else {
            return
        }
        guard let window else {
            return
        }

        let initialMouseLocation = NSEvent.mouseLocation
        let initialFrameOrigin = window.frame.origin
        var didDrag = false

        while true {
            guard let nextEvent = window.nextEvent(matching: [.leftMouseDragged, .leftMouseUp]) else {
                break
            }

            if nextEvent.type == .leftMouseUp {
                break
            }

            let currentMouseLocation = NSEvent.mouseLocation
            let deltaX = currentMouseLocation.x - initialMouseLocation.x
            let deltaY = currentMouseLocation.y - initialMouseLocation.y
            if !didDrag, abs(deltaX) + abs(deltaY) > 3 {
                didDrag = true
                dragDidBegin?()
            }
            guard didDrag else {
                continue
            }
            window.setFrameOrigin(NSPoint(
                x: initialFrameOrigin.x + deltaX,
                y: initialFrameOrigin.y + deltaY
            ))
        }

        if didDrag {
            dragDidEnd?(window.frame.origin)
        } else {
            clickHandler?()
        }
    }

    private func hasVisiblePixel(at point: NSPoint) -> Bool {
        guard bounds.contains(point) else {
            return false
        }
        guard
            let image,
            let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil)
        else {
            return true
        }

        let imageWidth = CGFloat(cgImage.width)
        let imageHeight = CGFloat(cgImage.height)
        let scale = min(bounds.width / imageWidth, bounds.height / imageHeight)
        let renderedSize = NSSize(width: imageWidth * scale, height: imageHeight * scale)
        let renderedRect = NSRect(
            x: bounds.minX + (bounds.width - renderedSize.width) / 2,
            y: bounds.minY + (bounds.height - renderedSize.height) / 2,
            width: renderedSize.width,
            height: renderedSize.height
        )
        guard renderedRect.contains(point), scale > 0 else {
            return false
        }

        let pixelX = Int((point.x - renderedRect.minX) / scale)
        let pixelY = Int((renderedRect.maxY - point.y) / scale)
        guard
            pixelX >= 0,
            pixelX < cgImage.width,
            pixelY >= 0,
            pixelY < cgImage.height
        else {
            return false
        }

        let bitmap = NSBitmapImageRep(cgImage: cgImage)
        return (bitmap.colorAt(x: pixelX, y: pixelY)?.alphaComponent ?? 0) > 0.05
    }
}

extension Array {
    var nonEmpty: [Element]? {
        isEmpty ? nil : self
    }
}

extension NSImage {
    func horizontallyFlipped() -> NSImage {
        let flipped = NSImage(size: size)
        flipped.lockFocus()
        let transform = NSAffineTransform()
        transform.translateX(by: size.width, yBy: 0)
        transform.scaleX(by: -1, yBy: 1)
        transform.concat()
        draw(
            in: NSRect(origin: .zero, size: size),
            from: NSRect(origin: .zero, size: size),
            operation: .sourceOver,
            fraction: 1.0
        )
        flipped.unlockFocus()
        return flipped
    }
}

func parsePackURL() -> URL {
    let arguments = CommandLine.arguments
    if let index = arguments.firstIndex(of: "--pack"), arguments.indices.contains(index + 1) {
        return URL(fileURLWithPath: arguments[index + 1], isDirectory: true).standardizedFileURL
    }
    if let resourceURL = Bundle.main.resourceURL {
        let bundledPackURL = resourceURL.appendingPathComponent("pets/default", isDirectory: true)
        if FileManager.default.fileExists(atPath: bundledPackURL.appendingPathComponent("pet.json").path) {
            return bundledPackURL.standardizedFileURL
        }
    }
    return URL(fileURLWithPath: "sample-pets/blueberry", isDirectory: true).standardizedFileURL
}

func isRunningAsAppBundle() -> Bool {
    Bundle.main.bundleURL.pathExtension == "app"
}

do {
    let loadedPack = try CodexPetPack.load(from: parsePackURL())
    let app = NSApplication.shared
    app.setActivationPolicy(isRunningAsAppBundle() ? .regular : .accessory)
    let delegate = PawbleAppDelegate(pack: loadedPack)
    app.delegate = delegate
    app.run()
} catch {
    fputs("Pawble failed to start: \(error.localizedDescription)\n", stderr)
    exit(1)
}
