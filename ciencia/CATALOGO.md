# Catálogo dos 115 arquivos científicos

Cada linha descreve a implementação delimitada, não o aceite de uma lei universal. Os exemplos de entrada ficam em `catalogo.json`.

| ID | Arquivo | Contrato e alcance |
|---|---|---|
| 1 | [mecanica_hamiltoniana.omega](fisica/mecanica_hamiltoniana.omega) | Energy-exact Cayley midpoint map for one quadratic oscillator, not arbitrary Hamiltonian flows. |
| 2 | [integrador_simplico_verlet.omega](fisica/integrador_simplico_verlet.omega) | Symplectic Verlet preserves a modified quadratic energy; physical-energy drift is reported, not set to zero. |
| 3 | [orbita_kepler_exata.omega](fisica/orbita_kepler_exata.omega) | Encloses the elliptic Kepler root and planar coordinates; no rational exact representation of general anomalies. |
| 4 | [tres_corpos_restrito.omega](fisica/tres_corpos_restrito.omega) | Interval CR3BP vector field, Jacobi value and L4 enclosure; not a certified long-time orbit integrator. |
| 5 | [pendulo_duplo_caotico.omega](fisica/pendulo_duplo_caotico.omega) | Rational enclosures of accelerations and optional measured finite-time separation; no asymptotic chaos proof. |
| 6 | [colisoes_rigidas_conservativas.omega](fisica/colisoes_rigidas_conservativas.omega) | Momentum is exact; kinetic energy is conserved only for elastic collisions, otherwise heat accounts for loss. |
| 7 | [termodinamica_gas_ideal.omega](fisica/termodinamica_gas_ideal.omega) | Ideal-gas constitutive model with exact equation of state and interval logarithmic entropy changes. |
| 8 | [gas_van_der_waals.omega](fisica/gas_van_der_waals.omega) | Exact van der Waals isotherm and analytic critical parameters; phase coexistence needs an additional construction. |
| 9 | [ciclo_carnot_reversivel.omega](fisica/ciclo_carnot_reversivel.omega) | Two equilibrium reservoirs, cyclic working fluid, positive absolute temperatures; no universal physical axiom is inferred. |
| 10 | [distribuicao_maxwell_boltzmann.omega](fisica/distribuicao_maxwell_boltzmann.omega) | Normalised discrete speed-grid approximation; continuous Maxwell density is not claimed rational/exact. |
| 11 | [modelo_ising_2d.omega](fisica/modelo_ising_2d.omega) | All configurations on finite 2..4 square tori; Boltzmann weights are enclosed, not irrational exact samples. |
| 12 | [maxwell_discreto_fdtd.omega](fisica/maxwell_discreto_fdtd.omega) | Periodic 2D TE Yee discretisation preserves discrete magnetic divergence; this is not a charge-conservation theorem. |
| 13 | [potencial_eletrostatico_poisson.omega](fisica/potencial_eletrostatico_poisson.omega) | Deterministic rational Gauss-Seidel with fixed boundary and measured residual, not a convergence-by-assertion solver. |
| 14 | [lei_snell_refracao_exata.omega](fisica/lei_snell_refracao_exata.omega) | Exact Snell sine relation and cosine enclosure; arbitrary angles are not rational numbers. |
| 15 | [propagacao_guias_onda.omega](fisica/propagacao_guias_onda.omega) | Perfect-conductor guide with conservative 3 < pi < 4 bounds; threshold ambiguity remains explicit. |
| 16 | [schrodinger_1d_discreto.omega](fisica/schrodinger_1d_discreto.omega) | Finite real symmetric Hamiltonian with Gershgorin bounds; two sites also get individual root enclosures. |
| 17 | [poco_potencial_infinito.omega](fisica/poco_potencial_infinito.omega) | Energy enclosures from 3 < pi < 4; pi and general energy levels are not silently made rational. |
| 18 | [oscilador_harmonico_quantico.omega](fisica/oscilador_harmonico_quantico.omega) | Rational unnormalised Fock basis with factorial metric; finite truncation cannot satisfy the infinite CCR exactly. |
| 19 | [spin_pauli_algebra.omega](fisica/spin_pauli_algebra.omega) | Exact Pauli expectations for pure two-component Q(i) states, normalised by their exact squared norm. |
| 20 | [geodesicas_schwarzschild.omega](fisica/geodesicas_schwarzschild.omega) | Exterior equatorial timelike geodesic field in G=c=1 units; mass-shell inconsistency is reported, not hidden. |
| 21 | [desvio_luz_gravitacional.omega](fisica/desvio_luz_gravitacional.omega) | Leading weak-field deflection plus a strong-field turning-point bracket; full strong-field bending is not claimed. |
| 22 | [equacao_friedmann.omega](fisica/equacao_friedmann.omega) | Flat homogeneous Friedmann model with explicit kappa (8*pi*G/3), matter/radiation scaling and root bounds. |
| 23 | [balanco_reacoes_redox.omega](quimica/balanco_reacoes_redox.omega) | Primitive positive integer null vector; include signed atom/isotope/charge rows explicitly. Ambiguous nullspaces are rejected. |
| 24 | [calculo_reagente_limitante.omega](quimica/calculo_reagente_limitante.omega) | Exact stoichiometric extent and nonnegative remainders; reaction feasibility/kinetics are separate obligations. |
| 25 | [estequiometria_combustao.omega](quimica/estequiometria_combustao.omega) | Atom-balanced complete or prescribed partial CO combustion; ignition and thermodynamic viability are not inferred. |
| 26 | [lei_hess_entalpia.omega](quimica/lei_hess_entalpia.omega) | Hess linear combination with exact target verification; input enthalpies remain empirical/model data. |
| 27 | [equilibrio_gibbs_minimizacao.omega](quimica/equilibrio_gibbs_minimizacao.omega) | Strictly convex ideal binary isomer mixture; interval closed-form minimizer, not a generic chemical Gibbs solver. |
| 28 | [constante_equilibrio_kp_kc.omega](quimica/constante_equilibrio_kp_kc.omega) | Dimensionless positive activities and explicit pressure/concentration normalisation; equality is exact only for supplied data. |
| 29 | [equilibrio_acido_base_tamponamento.omega](quimica/equilibrio_acido_base_tamponamento.omega) | Ideal activity-equals-concentration acid model with a rational hydrogen root bracket and interval pH. |
| 30 | [leis_velocidade_integradas.omega](quimica/leis_velocidade_integradas.omega) | Zero/first/second order models; first-order exponent and half-life are enclosed, not claimed rational constants. |
| 31 | [mecanismo_michaelis_menten.omega](quimica/mecanismo_michaelis_menten.omega) | Steady-state enzyme constitutive law with exact monotonic derivative and saturation check. |
| 32 | [arrhenius_energia_ativacao.omega](quimica/arrhenius_energia_ativacao.omega) | Arrhenius model on the checked exponential domain, using rational Taylor/remainder enclosures. |
| 33 | [equacao_nernst_exata.omega](quimica/equacao_nernst_exata.omega) | Positive dimensionless reaction quotient, explicit electron count and interval natural logarithm. |
| 34 | [leis_faraday_eletrolise.omega](quimica/leis_faraday_eletrolise.omega) | Exact charge-to-mass conversion conditional on supplied units/constants and unit Faradaic efficiency. |
| 35 | [cinetica_butler_volmer.omega](quimica/cinetica_butler_volmer.omega) | Ideal Butler-Volmer polarisation with interval exponential currents and explicit model parameters. |
| 36 | [indices_miller_redes.omega](quimica/indices_miller_redes.omega) | Cubic and three-index hexagonal reciprocal-metric formulae, returning spacing enclosures. |
| 37 | [fator_empacotamento_atomico.omega](quimica/fator_empacotamento_atomico.omega) | Hard-sphere ideal-cell geometry with pi/root enclosures; HCP uses the ideal c/a ratio. |
| 38 | [difracao_raios_x_bragg.omega](quimica/difracao_raios_x_bragg.omega) | Exact Bragg sine, forbidden-reflection detection, and conservative rational half-angle/atan enclosures. |
| 39 | [needleman_wunsch_exato.omega](biologia/needleman_wunsch_exato.omega) | Global affine-gap dynamic programming and deterministic traceback; byte sequences up to 128 bytes. |
| 40 | [smith_waterman_local.omega](biologia/smith_waterman_local.omega) | Smith-Waterman score and endpoint with two rows of memory; linear gaps, no reconstructed traceback. |
| 41 | [fm_index_bwt_aligner.omega](biologia/fm_index_bwt_aligner.omega) | Finite BWT/FM backward search with explicit sentinel and occurrence counts; bounded pedagogical suffix construction. |
| 42 | [montagem_debruijn_euler.omega](biologia/montagem_debruijn_euler.omega) | Spells one Eulerian traversal using every supplied kmer; repeats can make the original sequence nonunique. |
| 43 | [scoring_matrices_pam_blosum.omega](biologia/scoring_matrices_pam_blosum.omega) | Derives bounded log-odds from supplied counts and pseudocounts; does not invent published PAM/BLOSUM datasets. |
| 44 | [arvore_filogenetica_upgma.omega](biologia/arvore_filogenetica_upgma.omega) | Exact average-linkage UPGMA; molecular-clock/ultrametric suitability remains an input-model assumption. |
| 45 | [neighbor_joining_tree.omega](biologia/neighbor_joining_tree.omega) | Exact NJ Q-criterion and branch lengths; negative limbs from nonadditive data are reported without clamping. |
| 46 | [maxima_parcimonia_fitch.omega](biologia/maxima_parcimonia_fitch.omega) | Fitch minimum unit-change score for one DNA character on a supplied binary tree; ambiguity sets are supported. |
| 47 | [modelo_jukes_cantor.omega](biologia/modelo_jukes_cantor.omega) | Homogeneous JC69 correction with a checked saturation/log domain; empirical model applicability is not proved. |
| 48 | [lotka_volterra_presa_predador.omega](biologia/lotka_volterra_presa_predador.omega) | Positive bounded rational nonstandard map; reports continuous-integral drift instead of promising closed orbit preservation. |
| 49 | [crescimento_logistico_populacional.omega](biologia/crescimento_logistico_populacional.omega) | Rational Beverton-Holt logistic discretisation preserves [0,K]; it is not the exact continuous exponential solution. |
| 50 | [equilibrio_hardy_weinberg.omega](biologia/equilibrio_hardy_weinberg.omega) | Two-allele random-mating model without selection/migration/mutation; exact genotype sum and allele invariance. |
| 51 | [potencial_lennard_jones_molecular.omega](biologia/potencial_lennard_jones_molecular.omega) | Exact squared-distance potential and force on a pair; singular coincident positions are rejected. |
| 52 | [angulos_ramachandran_peptideos.omega](biologia/angulos_ramachandran_peptideos.omega) | Supplied empirical angle boxes and optional nonlocal hard-sphere clash tests; not a proof of protein fold viability. |
| 53 | [cinetica_transporte_membrana.omega](biologia/cinetica_transporte_membrana.omega) | Closed two-compartment Fick step with exact total amount and nonnegative-concentration guard. |
| 54 | [primalidade_miller_rabin_exata.omega](matematica/primalidade_miller_rabin_exata.omega) | Seven-base Miller-Rabin only for unsigned 64-bit integers; not a Lean primality certificate. |
| 55 | [fatoracao_pollard_rho.omega](matematica/fatoracao_pollard_rho.omega) | Bounded factor search; unresolved cofactors are explicit, never declared prime. |
| 56 | [curvas_elipticas_corpos_finitos.omega](matematica/curvas_elipticas_corpos_finitos.omega) | Nonsingular prime fields, exact group operations; infinity is the empty point. |
| 57 | [inverso_modular_euclides_estendido.omega](matematica/inverso_modular_euclides_estendido.omega) | Extended Euclid with coprimality/domain checks and exact modular verification. |
| 58 | [eliminacao_gauss_jordan_fracionaria.omega](matematica/eliminacao_gauss_jordan_fracionaria.omega) | RREF with row pivoting, rectangular matrices and explicit rank/pivot columns. |
| 59 | [determinante_algoritmo_bareiss.omega](matematica/determinante_algoritmo_bareiss.omega) | Fraction-free Bareiss with pivoting and a witness for every exact integer division. |
| 60 | [ortogonalizacao_gram_schmidt_exata.omega](matematica/ortogonalizacao_gram_schmidt_exata.omega) | Exact orthogonal unnormalised Q and unit-upper R; irrational unit normalisation is not faked. |
| 61 | [autovalores_qr_sem_drift.omega](matematica/autovalores_qr_sem_drift.omega) | Certified-formula rational enclosures for symmetric 2x2 spectra, not a generic exact QR algorithm. |
| 62 | [integracao_simpson_com_residuo.omega](matematica/integracao_simpson_com_residuo.omega) | Polynomial Simpson quadrature with an explicit supremum bound on the fourth derivative. |
| 63 | [zeros_funcoes_bissecao_rigorosa.omega](matematica/zeros_funcoes_bissecao_rigorosa.omega) | Polynomial continuity plus exact opposite signs brackets a root; no uniqueness assertion. |
| 64 | [extrapolacao_richardson.omega](matematica/extrapolacao_richardson.omega) | Central Richardson extrapolation with a safe polynomial fifth-derivative remainder bound. |
| 65 | [envoltoria_convexa_graham_scan.omega](matematica/envoltoria_convexa_graham_scan.omega) | Graham scan with exact orientation and independent supporting-halfplane checks; collinear sets are explicit. |
| 66 | [triangulacao_delaunay_incremental.omega](matematica/triangulacao_delaunay_incremental.omega) | Incremental Bowyer-Watson with exact in-circle predicates and deterministic cocircular handling. |
| 67 | [diagrama_voronoi_fortunes.omega](matematica/diagrama_voronoi_fortunes.omega) | Exact bounded Voronoi via half-plane clipping; intentionally not an irrational-event Fortune implementation. |
| 68 | [equacao_foguete_tsiolkovsky.omega](engenharia/equacao_foguete_tsiolkovsky.omega) | Ideal vacuum rocket equation, interval logarithms and mass-consistent staging; external gravity/drag losses omitted. |
| 69 | [reentrada_atmosferica_perfil.omega](engenharia/reentrada_atmosferica_perfil.omega) | Lumped one-step frozen-density reentry and Sutton-Graves-type heating enclosure; no flight safety certification. |
| 70 | [atitude_quaternions_espaciais.omega](engenharia/atitude_quaternions_espaciais.omega) | Rational Cayley rotation update preserves unit norm; it approximates, rather than equals, the angular-rate exponential. |
| 71 | [filtro_kalman_racional_discreto.omega](engenharia/filtro_kalman_racional_discreto.omega) | Rational Joseph update with exact positive-definite checks and all-principal-minor PSD process-noise validation. |
| 72 | [cinematica_direta_denavit_hartenberg.omega](engenharia/cinematica_direta_denavit_hartenberg.omega) | Exact homogeneous DH transforms parameterised by rational half-angle tangents; angles at the tangent pole need another chart. |
| 73 | [cinematica_inversa_geometrica.omega](engenharia/cinematica_inversa_geometrica.omega) | Both planar 2R elbow branches and reachability/singularity checks; arbitrary six-axis IK is explicitly unsupported. |
| 74 | [planejamento_trajetoria_quintica.omega](engenharia/planejamento_trajetoria_quintica.omega) | Exact six-boundary-condition quintic polynomial and position/velocity/acceleration samples. |
| 75 | [fluxo_potencia_newton_raphson.omega](engenharia/fluxo_potencia_newton_raphson.omega) | Damped Newton for quadratic resistive DC power flow; checks local contraction inequalities, not generic AC convergence. |
| 76 | [analise_curto_circuito_simetrico.omega](engenharia/analise_curto_circuito_simetrico.omega) | Balanced RMS positive-sequence fault calculation; breaker sizing is a model calculation, never a trip action. |
| 77 | [estabilidade_transiente_geradores.omega](engenharia/estabilidade_transiente_geradores.omega) | Single-machine swing model with interval force and energy accounting; no unproved global transient-stability claim. |
| 78 | [trelica_metodo_dos_nos.omega](engenharia/trelica_metodo_dos_nos.omega) | Exact force-density nodal solve; irrational member lengths produce axial-force enclosures, singular mechanisms fail. |
| 79 | [escoamento_tubulacoes_darcy_weisbach.omega](engenharia/escoamento_tubulacoes_darcy_weisbach.omega) | Laminar exact friction or enclosed Colebrook root; empirical transitional regime is explicitly rejected. |
| 80 | [pressao_hidrostatica_barragens.omega](engenharia/pressao_hidrostatica_barragens.omega) | Static vertical-wall hydrostatic load only; seepage, foundation, earthquakes and structural safety are separate models. |
| 81 | [EnergyConservationTheorem.lean](../formal/science_axioms/EnergyConservationTheorem.lean) | Quadratic mass/spring oscillator midpoint invariant and finite composition; not arbitrary Hamiltonian flows. |
| 82 | [SecondLawThermodynamics.lean](../formal/science_axioms/SecondLawThermodynamics.lean) | Entropy production hypothesis and two-reservoir Carnot consequence, not a derivation of the physical Second Law. |
| 83 | [SymplecticFormPreservation.lean](../formal/science_axioms/SymplecticFormPreservation.lean) | One-degree-of-freedom quadratic Verlet determinant for nonzero mass and symplectic bilinear form; not exact physical energy. |
| 84 | [LorentzInvariance.lean](../formal/science_axioms/LorentzInvariance.lean) | One spatial direction, c=1, rational representable boosts with explicit gamma normalisation. |
| 85 | [QuantumUnitarity.lean](../formal/science_axioms/QuantumUnitarity.lean) | Exact norm preservation for rational two-level rotations and proved coarse pi bounds. |
| 86 | [StoichiometricConservation.lean](../formal/science_axioms/StoichiometricConservation.lean) | Conserved rows may encode isotope/charge inventories; elemental balance alone does not encode nuclear/electron conservation. |
| 87 | [GibbsEnergyMinimality.lean](../formal/science_axioms/GibbsEnergyMinimality.lean) | Convex quadratic free-energy surrogate only; does not discharge the native ideal-mixture logarithmic minimizer. |
| 88 | [MassActionLawDerivation.lean](../formal/science_axioms/MassActionLawDerivation.lean) | Ideal two-species activity/potential equilibrium relation; not a universal chemical constitutive law. |
| 89 | [NeedlemanWunschOptimality.lean](../formal/science_axioms/NeedlemanWunschOptimality.lean) | Global optimality and attainability of the mathematical linear-gap Needleman-Wunsch recurrence; affine native refinement remains separate. |
| 90 | [DeBruijnEulerianEquivalence.lean](../formal/science_axioms/DeBruijnEulerianEquivalence.lean) | Certified nonuniqueness counterexample plus traversal edge count; balanced De Bruijn data do not uniquely recover the original genome. |
| 91 | [HardyWeinbergStability.lean](../formal/science_axioms/HardyWeinbergStability.lean) | Two-allele random mating algebra, probability normalisation and allele preservation under declared assumptions. |
| 92 | [TaylorErrorBoundTheorem.lean](../formal/science_axioms/TaylorErrorBoundTheorem.lean) | Real exp/log Taylor tail bounds with explicit order/domain/budget hypotheses; reuses the existing analytic kernel. |
| 93 | [NewtonRaphsonConvergence.lean](../formal/science_axioms/NewtonRaphsonConvergence.lean) | Quadratic squared-residual identity and safeguarded rational upper iterates; no division by zero or blanket convergence promise. |
| 94 | [BareissDivisionFreeTheorem.lean](../formal/science_axioms/BareissDivisionFreeTheorem.lean) | 3x3 Sylvester exact-division identity; general Bareiss loop is runtime-checked, not formally refined here. |
| 95 | [GrahamScanConvexity.lean](../formal/science_axioms/GrahamScanConvexity.lean) | Convexity of the exact supporting-halfplane certificate region; no unproved end-to-end native Graham refinement. |
| 96 | [LyapunovAsymptoticStability.lean](../formal/science_axioms/LyapunovAsymptoticStability.lean) | Scalar discrete linear asymptotic stability with &#124;gain&#124;<1; not arbitrary nonlinear-controller Lyapunov synthesis. |
| 97 | [KalmanCovariancePositiveDefinite.lean](../formal/science_axioms/KalmanCovariancePositiveDefinite.lean) | Strict positive scalar prior/noise guarantee posterior positivity; zero noise is an explicit counterexample to unconditional strictness. |
| 98 | [NyquistStabilityCriterion.lean](../formal/science_axioms/NyquistStabilityCriterion.lean) | First-order negative-feedback pole/Nyquist half-plane special case; not the general argument-principle criterion. |
| 99 | [gerador_hipoteses_fisicas.omega](../agentes_cientificos/gerador_hipoteses_fisicas.omega) | Exact bounded polynomial hypothesis fitting with held-out residuals; empirical fit is not a physical law. |
| 100 | [planejador_experimentos_quimicos.omega](../agentes_cientificos/planejador_experimentos_quimicos.omega) | Finite cost/toxicity route planning over supplied conserved inventories; conservation alone does not establish chemical viability. |
| 101 | [rastreador_literatura_formal.omega](../agentes_cientificos/rastreador_literatura_formal.omega) | Controlled CLAIM extraction with exact provenance; arbitrary papers and citations stay unverified data, never new axioms. |
| 102 | [motor_simulacao_multidisciplinar.omega](../agentes_cientificos/motor_simulacao_multidisciplinar.omega) | A declared closed oscillator/two-reservoir/isomer model with exact discrete total-energy and amount checks. |
| 103 | [validador_dimensional_unidades.omega](../agentes_cientificos/validador_dimensional_unidades.omega) | SI dimension graph with exact unit scales; additions require equal dimension vectors, multiplicative units only. |
| 104 | [despachante_provas_lean.omega](../agentes_cientificos/despachante_provas_lean.omega) | Renders bounded closed rational obligations only; the CPU supervisor actually compiles Lean and audits dependencies. |
| 105 | [agente_popper_falseador.omega](../agentes_cientificos/agente_popper_falseador.omega) | Produces exact counterexamples on a declared finite grid; failure to find one is not a universal proof. |
| 106 | [caçador_instabilidades_numericas.omega](../agentes_cientificos/caçador_instabilidades_numericas.omega) | Exact zero witnesses and conservative interval denominator checks; no division is attempted at singular states. |
| 107 | [injetor_ruido_sensores.omega](../agentes_cientificos/injetor_ruido_sensores.omega) | Deterministic finite-grid Gaussian-weight approximation; not a continuous exact Gaussian generator or cryptographic PRNG. |
| 108 | [emissor_artigo_executavel.omega](../agentes_cientificos/emissor_artigo_executavel.omega) | Self-contained hash-addressed article/source/binary-hex/proof container; hashing does not authenticate or prove the artifacts. |
| 109 | [gerador_graficos_vetoriais_svg.omega](../agentes_cientificos/gerador_graficos_vetoriais_svg.omega) | Deterministic SVG polyline with exact raw-data hash and explicit 1e-6 display quantisation; no false exact decimal rendering. |
| 110 | [registro_descoberta_blockchain.omega](../agentes_cientificos/registro_descoberta_blockchain.omega) | Prepares real digest anchor payloads; no transaction is broadcast, fee spent, or fabricated inclusion/timestamp accepted. |
| 111 | [tensor_calculus.omega](../std/math/tensor_calculus.omega) | Pointwise tensor contractions and Christoffel symbols; curvature requires caller-supplied consistent connection derivatives. |
| 112 | [complex_rational.omega](../std/math/complex_rational.omega) | Field arithmetic over Q(i), exact squared norm and zero-denominator rejection. |
| 113 | [csv_dataset_parser.omega](../std/io/csv_dataset_parser.omega) | Bounded quoted CSV with escaped quotes/newlines and optional exact scalar conversion; byte delimiter semantics. |
| 114 | [spatial_kdtree.omega](../std/collections/spatial_kdtree.omega) | Balanced median-split KD-tree and exact squared-distance pruning; bounded static point sets, deterministic ties. |
| 115 | [quantum_gate_emulator.omega](../runtime/quantum_gate_emulator.omega) | Sparse exact Q(i) gates up to 32 address bits with active-amplitude quota; H/T and dense 2^32 storage are not falsely supported. |
